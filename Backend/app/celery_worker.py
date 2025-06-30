from celery import Celery
from app.core.config import settings

# Create a Celery instance.
# The first argument is the name of the current module.
# The 'broker' argument specifies the URL of the message broker (Redis).
# The 'backend' argument is where Celery stores task results (we'll also use Redis).
celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL, # <-- Use the setting
    backend=settings.CELERY_BROKER_URL # <-- Use the setting
)

# Tell Celery where to find our tasks.
# It will look for a 'tasks' variable inside the 'drive_uploader_task' module.
celery_app.conf.update(
    imports=('app.tasks.drive_uploader_task',),
    task_track_started=True
)