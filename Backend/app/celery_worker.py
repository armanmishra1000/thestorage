# from celery import Celery
# from app.core.config import settings # <-- Make sure this is imported

# celery_app = Celery(
#     "tasks",
#     broker=settings.CELERY_BROKER_URL,
#     backend=settings.CELERY_BROKER_URL
# )
# # Tell Celery where to find our tasks.
# # It will look for a 'tasks' variable inside the 'drive_uploader_task' module.
# celery_app.conf.update(
#     # Add the new task module to the list of imports
#     imports=(
#         'app.tasks.drive_uploader_task',
#         'app.tasks.telegram_uploader_task'  
#     ),
#     task_track_started=True
# )


from celery import Celery
from app.core.config import settings
from kombu import Queue

celery_app = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_BROKER_URL
)

# --- THIS IS THE NEW, KEY CONFIGURATION ---
# 1. Define the two queues we need.
celery_app.conf.task_queues = (
    Queue('uploads_queue', routing_key='task.upload'),
    Queue('archive_queue', routing_key='task.archive'),
)

# 2. Define routing rules. This tells Celery which tasks go to which queue.
celery_app.conf.task_routes = {
    'tasks.upload_to_drive': {'queue': 'uploads_queue', 'routing_key': 'task.upload'},
    'tasks.transfer_to_telegram': {'queue': 'archive_queue', 'routing_key': 'task.archive'},
    'tasks.finalize_and_delete': {'queue': 'archive_queue', 'routing_key': 'task.archive'},
}
# --- END OF NEW CONFIGURATION ---

# Tell Celery where to find our tasks.
celery_app.conf.update(
    imports=(
        'app.tasks.drive_uploader_task',
        'app.tasks.telegram_uploader_task'  
    ),
    task_track_started=True
)