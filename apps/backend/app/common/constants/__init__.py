"""Application-wide constants."""

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100

# Gamification
MATCH_POINTS = 10          # Points awarded per candidate match
BADGE_SPEED_DEMON = "speed_demon"        # 5+ matches in a day
BADGE_QUALITY_SOURCER = "quality_sourcer"  # 3+ accepted candidates in a week

BADGE_THRESHOLDS = {
    BADGE_SPEED_DEMON: 5,     # daily matches
    BADGE_QUALITY_SOURCER: 3, # weekly accepted
}

# Pipeline
PIPELINE_STATUSES = ("pending", "accepted", "rejected")

# Storage (Cloudinary)
RESUME_FOLDER = "eigensu/resumes"
RESUME_UPLOAD_PRESET = "eigensu_resumes"
ALLOWED_RESUME_FORMATS = ("pdf", "doc", "docx")
MAX_RESUME_SIZE_MB = 10
