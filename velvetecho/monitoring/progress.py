"""Progress tracking for workflows and activities"""

from typing import Dict, Any, Optional, Callable
from temporalio import activity
import structlog

logger = structlog.get_logger(__name__)


class ProgressTracker:
    """
    Helper for tracking and reporting progress from activities.

    Features:
    - Automatic heartbeat with progress data
    - Structured progress messages
    - Optional external callbacks (SSE, webhooks, etc.)

    Example:
        @activity
        async def process_files(file_paths: List[str]):
            tracker = ProgressTracker(total=len(file_paths))

            for file_path in file_paths:
                tracker.start_item(file_path, "processing")
                result = await process_file(file_path)
                tracker.complete_item(file_path, "completed")

            return tracker.get_summary()
    """

    def __init__(
        self,
        total: int,
        callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.total = total
        self.completed = 0
        self.failed = 0
        self.current_item = None
        self.callback = callback

    def start_item(self, item_id: str, status: str = "started", **metadata):
        """Mark item as started"""
        self.current_item = item_id

        progress = {
            "item_id": item_id,
            "status": status,
            "progress": {
                "completed": self.completed,
                "failed": self.failed,
                "total": self.total,
                "percentage": int((self.completed / self.total) * 100),
            },
            **metadata,
        }

        # Send heartbeat
        try:
            activity.heartbeat(progress)
        except RuntimeError:
            # Not in activity context (testing)
            pass

        # External callback
        if self.callback:
            self.callback(progress)

        logger.info("Progress: started item", **progress)

    def complete_item(self, item_id: str, status: str = "completed", **metadata):
        """Mark item as completed"""
        self.completed += 1
        self.current_item = None

        progress = {
            "item_id": item_id,
            "status": status,
            "progress": {
                "completed": self.completed,
                "failed": self.failed,
                "total": self.total,
                "percentage": int((self.completed / self.total) * 100),
            },
            **metadata,
        }

        # Send heartbeat
        try:
            activity.heartbeat(progress)
        except RuntimeError:
            pass

        # External callback
        if self.callback:
            self.callback(progress)

        logger.info("Progress: completed item", **progress)

    def fail_item(self, item_id: str, error: str, **metadata):
        """Mark item as failed"""
        self.failed += 1
        self.current_item = None

        progress = {
            "item_id": item_id,
            "status": "failed",
            "error": error,
            "progress": {
                "completed": self.completed,
                "failed": self.failed,
                "total": self.total,
                "percentage": int(((self.completed + self.failed) / self.total) * 100),
            },
            **metadata,
        }

        # Send heartbeat
        try:
            activity.heartbeat(progress)
        except RuntimeError:
            pass

        # External callback
        if self.callback:
            self.callback(progress)

        logger.error("Progress: failed item", **progress)

    def get_summary(self) -> Dict[str, Any]:
        """Get progress summary"""
        return {
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "percentage": int(((self.completed + self.failed) / self.total) * 100),
        }
