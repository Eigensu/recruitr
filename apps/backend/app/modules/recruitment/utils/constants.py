"""Recruitment domain constants."""

from app.modules.recruitment.enums.department import Department

# Every resume upload — the bulk upload and the resume-to-lead drafts — takes at
# most this many files, each at most this size. Files are processed one after
# another in a single request (text extraction, then a Cloudinary upload), so 20
# keeps a batch well under a minute; 5 MB fits any text resume, and a scanned
# PDF that doesn't would have nothing to parse anyway. Mirrored in the
# frontend's lib/constants/uploads.ts.
RESUME_BATCH_MAX_FILES = 20
RESUME_MAX_BYTES = 5 * 1024 * 1024

# Cities a resume's city is matched against — the same list the candidate forms
# offer (lib/constants/candidate.ts CITIES), plus the spellings people write.
RESUME_CITY_ALIASES: dict[str, str] = {
    "mumbai": "Mumbai",
    "navi mumbai": "Mumbai",
    "thane": "Mumbai",
    "bombay": "Mumbai",
    "delhi": "Delhi",
    "new delhi": "Delhi",
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore",
    "hyderabad": "Hyderabad",
    "pune": "Pune",
    "goa": "Goa",
    "chennai": "Chennai",
    "kolkata": "Kolkata",
    "ahmedabad": "Ahmedabad",
    "jaipur": "Jaipur",
}

ROLES_BY_CATEGORY = {
    Department.service: [
        "Bar Assistant",
        "Bar Manager",
        "Bar Supervisor",
        "Barback",
        "Barista",
        "Bartender",
        "Café Manager",
        "Café Supervisor",
        "Captain",
        "Cashier",
        "Counter Sales",
        "Duty Manager",
        "F&B Executive",
        "F&B Supervisor",
        "Floor Supervisor",
        "Front Office Executive",
        "GRE",
        "Hostess",
        "Mixologist",
        "Outlet Manager",
        "Shift Manager",
        "Sommelier",
        "Steward",
        "Waiter / Server",
        "RM",
        "ARM",
        "Head Bartender",
        "Beverage Head",
    ],
    Department.boh: [
        "CDP",
        "Commi 1",
        "Commi 2",
        "Commi 3",
        "DCDP",
        "Executive Chef",
        "Food Production Manager",
        "Head Baker",
        "Head Chef",
        "Kitchen Supervisor",
        "Packaging Assistant",
        "Sous Chef",
        "Staff Cook",
        "Store Manager",
        "Storekeeper",
    ],
    Department.corporate: [
        "Accountant / Accounts",
        "Admin / Back Office",
        "Brand Manager",
        "Business Development",
        "Community Manager",
        "Content Strategist",
        "CRM",
        "Data Analyst",
        "EA / PA",
        "F&B Controller",
        "General Manager",
        "Graphic Designer",
        "HR",
        "Lawyer",
        "Marketing",
        "MIS Executive",
        "Operations Head",
        "Payroll",
        "PR",
        "Project Manager",
        "Purchase",
        "Sales",
        "Social Media",
        "Supply Chain / SCM",
        "Training Manager / L&D",
    ],
}
