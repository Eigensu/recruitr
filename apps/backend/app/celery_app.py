from celery import Celery

from app.config import settings

celery_app = Celery(
    "eigensu",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.modules.leaderboard.tasks.activity_tasks",
        "app.modules.leaderboard.tasks.badge_tasks",
        "app.modules.leaderboard.tasks.periodic_tasks",
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
            "schedule": 300.0,
        },
        "leaderboard-monthly-snapshot": {
            "task": "leaderboard.create_monthly_snapshot",
            "schedule": 86400.0,
        },
    },
)