"""Rule-based resume parser — extracts structured fields from raw PDF text.

Extracts: name, email, phone, city, current role (and its department),
experience_years, previous_company, skills. Skills are extracted from an
explicit Skills section first; any term from the domain vocabulary that appears
elsewhere in the text is appended.

Name, city and role are best-effort prefill for a form a person reviews; each
one returns None rather than a guess it can't stand behind.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from app.modules.recruitment.enums import Department, EducationLevel, Gender
from app.modules.recruitment.utils.constants import RESUME_CITY_ALIASES, ROLES_BY_CATEGORY

# ── Regex ──────────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.IGNORECASE)

_PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s.\-]?)?(?:\(?\d{2,4}\)?[\s.\-]?)?\d{3,4}[\s.\-]?\d{3,4}")

# An Indian mobile: optional +91 / 91 / 0, then ten digits starting 6–9, written
# whole or in the usual 5+5 split ("+91 98198 44180", "098198-44180"). Tried
# before _PHONE_RE, whose last group takes at most four digits and so cut the
# fifth off every 5+5 number — leaving a different, wrong number to call.
_IN_MOBILE_RE = re.compile(r"(?<![\d+])(?:\+?91[\s\-]?|0)?[6-9]\d{4}[\s\-]?\d{5}(?!\d)")

# "5 years", "5+ years of experience", "5 yrs exp" etc.
_EXPLICIT_EXP_RE = re.compile(
    r"(\d+)\s*\+?\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp\b)?",
    re.IGNORECASE,
)

# Date ranges: "Jan 2019 – Present", "2019-2022", "2019 to present"
_DATE_RANGE_RE = re.compile(
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"((?:19|20)\d{2})"
    r"\s*[-–—to]+\s*"
    r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)

# Section headers: "Skills", "Technical Skills", "Core Skills" etc.
_SKILLS_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:technical\s+|core\s+|key\s+|professional\s+)?skills?\s*[:\n]",
    re.IGNORECASE,
)

# Experience / Work section headers
_EXP_SECTION_RE = re.compile(
    r"(?:^|\n)\s*(?:work\s+)?(?:experience|employment|work\s+history)\s*[:\n]",
    re.IGNORECASE,
)

# Generic section boundary — used to bound skill extraction
_SECTION_BOUNDARY_RE = re.compile(
    r"\n\s*(?:education|work|experience|employment|projects?|certifications?|"
    r"references?|summary|objective|profile|awards?|achievements?|languages?|"
    r"hobbies|interests)\s*[:\n]",
    re.IGNORECASE,
)

# Education Level Extractors
_EDU_PHD_RE = re.compile(r"\b(ph\.?d|doctorate)\b", re.IGNORECASE)
_EDU_MASTERS_RE = re.compile(r"\b(master'?s|m\.?a\.|m\.?s\.|mba|msc)\b", re.IGNORECASE)
_EDU_BACHELORS_RE = re.compile(
    r"\b(bachelor'?s|b\.?a\.|b\.?s\.|bsc|btech|b\.?e\.|undergrad(?:uate)?)\b",
    re.IGNORECASE,
)
_EDU_HS_RE = re.compile(r"\b(high school|diploma|hsc|ssc|12th|10th)\b", re.IGNORECASE)

# ── Domain skill vocabulary ────────────────────────────────────────────────────
# Matched against full resume text when no explicit Skills section is found,
# or to supplement skills extracted from the section.

_SKILL_VOCAB: frozenset[str] = frozenset(
    {
        # F&B / Café
        "barista",
        "espresso",
        "coffee",
        "latte art",
        "cappuccino",
        "brewing",
        "pour over",
        "french press",
        "cold brew",
        "aeropress",
        "siphon brewing",
        "food safety",
        "haccp",
        "food hygiene",
        "servsafe",
        "kitchen",
        "cooking",
        "baking",
        "pastry",
        "grilling",
        "menu planning",
        "food costing",
        "bartending",
        "mixology",
        "cocktails",
        "wine",
        "catering",
        "banquets",
        # Restaurant ops
        "pos systems",
        "micros",
        "toast pos",
        "inventory management",
        "front of house",
        "back of house",
        "cash handling",
        "table service",
        "upselling",
        # Hospitality / General
        "customer service",
        "hospitality",
        "guest relations",
        "complaint handling",
        "team management",
        "staff training",
        "scheduling",
        "budgeting",
        "reporting",
        "events management",
        # Operations / HR
        "recruitment",
        "onboarding",
        "hr",
        "human resources",
        "operations",
        "logistics",
        "supply chain",
        "procurement",
        "quality control",
        "compliance",
        # General professional
        "communication",
        "teamwork",
        "leadership",
        "management",
        "sales",
        "marketing",
        "social media",
        "branding",
        "microsoft office",
        "excel",
        "powerpoint",
        "data entry",
    }
)


# ── Result ──────────────────────────────────────────────────────────────────────


@dataclass
class ParsedResume:
    email: str | None = None
    phone: str | None = None
    experience_years: float | None = None
    previous_company: str | None = None
    education_level: EducationLevel | None = None
    city: str | None = None
    age: int | None = None
    gender: Gender | None = None
    tags: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    full_name: str | None = None
    current_role: str | None = None  # a role from ROLES_BY_CATEGORY, as written there
    department: Department | None = None  # the department that role belongs to


# ── Name, city, role ───────────────────────────────────────────────────────────

# Words that sit at the top of a resume but are never someone's name.
_NOT_A_NAME = {
    "resume",
    "curriculum",
    "vitae",
    "cv",
    "biodata",
    "profile",
    "objective",
    "summary",
    "contact",
    "personal",
    "details",
    "career",
    "experience",
    "education",
    "skills",
    "address",
    "mobile",
    "phone",
    "email",
}
_NAME_WORD = re.compile(r"^[A-Za-z][A-Za-z.'\-]*$")
_NAME_LINES_SCANNED = 8


def _extract_name(text: str) -> str | None:
    """The candidate's name: the first short line near the top made only of words.

    Resumes almost always open with the name. Anything with a digit, an @, a
    colon or a resume heading is skipped, and only 2–4 words are accepted — a
    sentence or a single word ("Resume") is not a name.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:_NAME_LINES_SCANNED]:
        if any(ch.isdigit() for ch in line) or "@" in line or ":" in line:
            continue
        words = line.replace(",", " ").split()
        if not 2 <= len(words) <= 4:
            continue
        if any(w.lower().strip(".") in _NOT_A_NAME for w in words):
            continue
        if all(_NAME_WORD.match(w) for w in words):
            # "SHAWN DSOUZA" and "shawn dsouza" both come out as "Shawn Dsouza".
            return " ".join(w if w.isupper() and len(w) <= 2 else w.capitalize() for w in words)
    return None


_CITY_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, RESUME_CITY_ALIASES), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _extract_city(text: str) -> str | None:
    """The first known city mentioned, as the candidate forms spell it."""
    match = _CITY_RE.search(text)
    return RESUME_CITY_ALIASES[match.group(1).lower()] if match else None


def _role_patterns() -> list[tuple[re.Pattern[str], str, Department]]:
    # Longest first, so "Bar Manager" wins over "Manager"-like shorter names.
    roles = [
        (role, department) for department, names in ROLES_BY_CATEGORY.items() for role in names
    ]
    roles.sort(key=lambda item: len(item[0]), reverse=True)
    return [
        (re.compile(r"\b" + re.escape(role) + r"\b", re.IGNORECASE), role, department)
        for role, department in roles
    ]


_ROLES = _role_patterns()


def _extract_role(text: str) -> tuple[str | None, Department | None]:
    """The earliest catalogue role named in the resume, and its department.

    Earliest, because a resume leads with the current or most recent job. Only
    roles from the catalogue are returned, so the value drops straight into the
    form's role dropdown.
    """
    best: tuple[int, str, Department] | None = None
    for pattern, role, department in _ROLES:
        match = pattern.search(text)
        if match and (best is None or match.start() < best[0]):
            best = (match.start(), role, department)
    return (best[1], best[2]) if best else (None, None)


# ── Internal helpers ───────────────────────────────────────────────────────────


def extract_email(text: str) -> str | None:
    """First email address in the text.

    Public because bulk upload identifies candidates by it and needs that one
    field even when the brand has full resume parsing turned off.
    """
    m = _EMAIL_RE.search(text)
    return m.group(0).lower() if m else None


def _extract_phone(text: str) -> str | None:
    mobile = _IN_MOBILE_RE.search(text)
    if mobile:
        return mobile.group(0).strip()
    # Anything else (landlines, other countries): the general pattern.
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 7 <= len(digits) <= 15:
            return m.group(0).strip()
    return None


def _extract_experience_years(text: str) -> float | None:
    m = _EXPLICIT_EXP_RE.search(text)
    if m:
        return float(m.group(1))

    # Infer from date ranges: span from earliest start to latest end
    current_year = date.today().year
    years: list[int] = []
    end_years: list[int] = []
    for m in _DATE_RANGE_RE.finditer(text):
        years.append(int(m.group(1)))
        raw_end = m.group(2).lower()
        end_years.append(current_year if raw_end in ("present", "current", "now") else int(raw_end))

    if not years:
        return None
    span = max(end_years) - min(years)
    return float(max(0, span))


def _extract_previous_company(text: str) -> str | None:
    """Return the first plausible company name found after a Work Experience header."""
    m = _EXP_SECTION_RE.search(text)
    if not m:
        return None

    section = text[m.end() : m.end() + 600]
    for line in section.splitlines():
        line = line.strip()
        if not line or len(line) < 3 or len(line) > 80:
            continue
        # Skip lines that are dates, job titles with keywords, or bullets
        if re.search(r"\b(19|20)\d{2}\b", line):
            continue
        if re.match(r"^[-•*·]", line):
            continue
        if re.search(
            r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|present|current)\b",
            line,
            re.IGNORECASE,
        ):
            continue
        # Company names typically have at least one capital letter
        if re.search(r"[A-Z]", line):
            return line
    return None


def _extract_skills(text: str) -> list[str]:
    skills: list[str] = []

    # 1. Explicit Skills section
    sm = _SKILLS_SECTION_RE.search(text)
    if sm:
        section_start = sm.end()
        boundary = _SECTION_BOUNDARY_RE.search(text, section_start)
        section_end = boundary.start() if boundary else section_start + 600
        section_text = text[section_start:section_end]

        for token in re.split(r"[,\n•·\-–|/]", section_text):
            token = re.sub(r"[^\w\s]", "", token).strip().lower()
            if 2 <= len(token) <= 60 and not re.match(r"^\d+$", token):
                skills.append(token)

    # 2. Vocabulary matching across the full text
    text_lower = text.lower()
    for skill in sorted(_SKILL_VOCAB):  # sorted for determinism
        if skill not in skills and re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
            skills.append(skill)

    # Deduplicate preserving order, cap at 60
    seen: set[str] = set()
    unique: list[str] = []
    for s in skills:
        if s and s not in seen:
            seen.add(s)
            unique.append(s)
    return unique[:60]


def _extract_education_level(text: str) -> EducationLevel | None:
    # Match highest degree first
    if _EDU_PHD_RE.search(text):
        return EducationLevel.phd
    if _EDU_MASTERS_RE.search(text):
        return EducationLevel.masters
    if _EDU_BACHELORS_RE.search(text):
        return EducationLevel.bachelors
    if _EDU_HS_RE.search(text):
        return EducationLevel.high_school
    return None


# ── Public API ─────────────────────────────────────────────────────────────────


def parse_resume(text: str) -> ParsedResume:
    """Extract structured fields from raw PDF text."""
    skills = _extract_skills(text)
    current_role, department = _extract_role(text)
    return ParsedResume(
        email=extract_email(text),
        phone=_extract_phone(text),
        experience_years=_extract_experience_years(text),
        previous_company=_extract_previous_company(text),
        education_level=_extract_education_level(text),
        skills=skills,
        tags=skills[:5],  # Take top 5 extracted skills as AI tags
        full_name=_extract_name(text),
        city=_extract_city(text),
        current_role=current_role,
        department=department,
    )
