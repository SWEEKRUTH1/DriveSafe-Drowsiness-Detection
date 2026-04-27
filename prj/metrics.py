"""
Prometheus configuration and metrics
Monitoring and observability setup
"""

import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


class MetricsCollector:
    """Collects application metrics for monitoring."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.frame_count = 0
        self.fps = 0.0
        self.faces_detected_total = 0
        self.alerts_triggered = 0
        self.errors_count = 0
        self.start_time = time.time()
        self.frame_times = []
        
    def record_frame(self, face_count: int = 0, alert_triggered: bool = False,
                    error_occurred: bool = False):
        """Record frame metrics."""
        self.frame_count += 1
        
        if face_count > 0:
            self.faces_detected_total += face_count
        
        if alert_triggered:
            self.alerts_triggered += 1
        
        if error_occurred:
            self.errors_count += 1
        
        # Calculate FPS
        self.frame_times.append(time.time())
        if len(self.frame_times) > 30:
            self.frame_times.pop(0)
        
        if len(self.frame_times) > 1:
            time_diff = self.frame_times[-1] - self.frame_times[0]
            if time_diff > 0:
                self.fps = (len(self.frame_times) - 1) / time_diff
    
    def get_metrics(self) -> dict:
        """Get current metrics."""
        uptime = time.time() - self.start_time
        
        return {
            'frame_count': self.frame_count,
            'fps': round(self.fps, 2),
            'faces_detected_total': self.faces_detected_total,
            'alerts_triggered': self.alerts_triggered,
            'errors': self.errors_count,
            'uptime_seconds': round(uptime, 2),
            'avg_faces_per_frame': round(self.faces_detected_total / max(self.frame_count, 1), 2),
        }
    
    def reset(self):
        """Reset metrics."""
        self.frame_count = 0
        self.fps = 0.0
        self.faces_detected_total = 0
        self.alerts_triggered = 0
        self.errors_count = 0
        self.start_time = time.time()
        self.frame_times = []


def timer(func: Callable) -> Callable:
    """Decorator to measure function execution time."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.debug(f"{func.__name__} executed in {elapsed*1000:.2f}ms")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} failed after {elapsed*1000:.2f}ms: {str(e)}")
            raise
    
    return wrapper


# Global metrics instance
metrics = MetricsCollector()
