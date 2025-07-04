from celery import Celery
from app.core.config import settings # <-- Make sure this is imported

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL
)
# Tell Celery where to find our tasks.
# It will look for a 'tasks' variable inside the 'drive_uploader_task' module.
celery_app.conf.update(
    # Add the new task module to the list of imports
    imports=(
        'app.tasks.drive_uploader_task',
        'app.tasks.telegram_uploader_task'  
    ),
    task_track_started=True
)