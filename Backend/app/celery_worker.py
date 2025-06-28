from celery import Celery

# Create a Celery instance.
# The first argument is the name of the current module.
# The 'broker' argument specifies the URL of the message broker (Redis).
# The 'backend' argument is where Celery stores task results (we'll also use Redis).
celery_app = Celery(
    "tasks",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

# Tell Celery where to find our tasks.
# It will look for a 'tasks' variable inside the 'drive_uploader_task' module.
celery_app.conf.update(
    imports=('app.tasks.drive_uploader_task',),
    task_track_started=True
)