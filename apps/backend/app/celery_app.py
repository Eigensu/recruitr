from datetime import timedelta

from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.modules.leaderboard.tasks.activity_tasks",
        "app.modules.leaderboard.tasks.badge_tasks",
        "app.modules.leaderboard.tasks.periodic_tasks",
        "app.modules.dashboard.tasks",
        "app.modules.recruitment.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "leaderboard-refresh-cache": {
            "task": "leaderboard.refresh_cache",
            "schedule": timedelta(seconds=300),
        },
        "leaderboard-monthly-snapshot": {
            "task": "leaderboard.create_monthly_snapshot",
            "schedule": crontab(minute=0, hour=0, day_of_month=1),
        },
        "dashboard-daily-referee-processor": {
            "task": "dashboard.daily_referee_processor",
            "schedule": crontab(minute=0, hour=1),  # Runs daily at 01:00 UTC
        },
        "recruitment-reminders": {
            "task": "recruitment.process_reminders",
            "schedule": crontab(minute=30, hour=1),  # Runs daily at 01:30 UTC
        },
        "recruitment-joining-dates": {
            "task": "recruitment.process_joining_dates",
            "schedule": crontab(minute=0, hour=2),  # Runs daily at 02:00 UTC
        },
    },
)
