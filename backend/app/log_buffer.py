"""In-memory ring-buffer log handler for remote log viewing."""
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class LogEntry:
    timestamp: str
    level: str
    logger_name: str
    message: str


class RingBufferHandler(logging.Handler):
    """Logging handler that stores the last N log records in memory."""

    def __init__(self, capacity: int = 500):
        super().__init__()
        self.buffer: deque[LogEntry] = deque(maxlen=capacity)

    def emit(self, record: logging.LogRecord) -> None:
        entry = LogEntry(
            timestamp=datetime.fromtimestamp(record.created).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            level=record.levelname,
            logger_name=record.name,
            message=self.format(record),
        )
        self.buffer.append(entry)

    def get_entries(
        self,
        limit: int = 100,
        level: str | None = None,
        logger_filter: str | None = None,
    ) -> list[LogEntry]:
        entries = list(self.buffer)
        if level:
            level_upper = level.upper()
            entries = [e for e in entries if e.level == level_upper]
        if logger_filter:
            entries = [e for e in entries if logger_filter in e.logger_name]
        return entries[-limit:]


log_buffer_handler = RingBufferHandler(capacity=1000)
log_buffer_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                      datefmt="%Y-%m-%d %H:%M:%S")
)
