import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from ..config.settings import settings


class JSONFormatter(logging.Formatter):
    """Custom logging formatter that outputs log records as JSON lines."""

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
            "message": record.getMessage(),
        }

        # Dynamically append any extra key-value pairs passed in extra={}
        # Ignore standard LogRecord attributes
        standard_attrs = {
            "args", "asctime", "created", "exc_info", "exc_text", "filename",
            "funcName", "levelname", "levelno", "lineno", "module", "msecs",
            "message", "msg", "name", "pathname", "process", "processName",
            "relativeCreated", "stack_info", "thread", "threadName"
        }
        
        for key, value in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                log_record[key] = value

        # Include traceback details if an exception occurred
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging(name: str = "job_tracker") -> logging.Logger:
    """Configures JSON logging for both stdout and log files.

    Args:
        name: Name of the logger.

    Returns:
        A configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Ensure log directory exists
    log_file = Path(settings.log_file_path)
    log_file.parent.mkdir(parents=True, exist_ok=True)

    json_formatter = JSONFormatter()

    # Console Handler (writes to stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(json_formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File Handler (writes to logs/agent.log)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(json_formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    logger.propagate = False

    return logger


# Instantiate global logger
logger = setup_logging()
