import redis
import json
from app.core.config import settings

# Create a reusable Redis connection pool
# decode_responses=True is important for getting strings from Redis
redis_pool = redis.ConnectionPool.from_url(settings.CELERY_BROKER_URL, decode_responses=True)

class ProgressManager:
    def __init__(self, file_id: str):
        # Each file gets its own unique channel name
        self.channel_name = f"progress_{file_id}"
        self.redis_conn = redis.Redis(connection_pool=redis_pool)

    def publish_progress(self, percentage: int):
        """Publishes a progress update message."""
        message = {"type": "progress", "value": percentage}
        self.redis_conn.publish(self.channel_name, json.dumps(message))
        print(f"[PROGRESS_MANAGER] Published to {self.channel_name}: {message}")

    def publish_success(self, download_link: str):
        """Publishes the final success message with the download link."""
        # For now, the download link will be a simple path. We'll build the full URL on the frontend.
        # In a real app, this would be a more robust URL.
        message = {"type": "success", "value": download_link}
        self.redis_conn.publish(self.channel_name, json.dumps(message))
        print(f"[PROGRESS_MANAGER] Published to {self.channel_name}: {message}")

    def publish_error(self, error_message: str):
        """Publishes an error message."""
        message = {"type": "error", "value": error_message}
        self.redis_conn.publish(self.channel_name, json.dumps(message))
        print(f"[PROGRESS_MANAGER] Published to {self.channel_name}: {message}")