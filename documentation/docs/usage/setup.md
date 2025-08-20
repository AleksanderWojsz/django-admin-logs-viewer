---
sidebar_position: 2
hide_table_of_contents: true
---

# Setup

#### 1. Install package
```python
pip install django-admin-logs-viewer
```

#### 2. In `settings.py`:
```python
INSTALLED_APPS = [
    'django_admin_logs_viewer', # At this line at the top
    'django.contrib.admin',
    ...
]
```


```python
TEMPLATES = [
    {
        ...
        'OPTIONS': {
            ...
            'context_processors': [
                ...
                'django_admin_logs_viewer.context_processors.logs_url', # Add this line
            ],
        },
    },
]
```

#### 3. Example *LOGGING* configuration:
```python
LOGS_SAVE_PATH = BASE_DIR / 'logs'
(LOGS_SAVE_PATH / 'commands').mkdir(parents=True, exist_ok=True)
(LOGS_SAVE_PATH / 'other').mkdir(parents=True, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": '{{ "level": "{levelname}", "datetime": "{asctime}", "source": "{name}", "file": "{filename}:{lineno}", "message": "{message}" }}',
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {filename} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file_commands": {
            "level": "DEBUG",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_SAVE_PATH / 'commands' / 'logfile_commands.log',
            "when": "midnight",
            "interval": 1,
            "delay": True,
            "formatter": "verbose",
        },
        "file_other": {
            "level": "INFO",
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": LOGS_SAVE_PATH / 'other' / 'logfile_other.log',
            "when": "midnight",
            "interval": 1,
            "delay": True,
            "formatter": "verbose",
        },
    },
    "loggers": {
        "your_app.management.commands": {
            "level": "DEBUG",
            "handlers": ["file_commands", "console"],
            "propagate": False,
        },
        "": {
            "level": "DEBUG",
            "handlers": ["file_other", "console"],
            "propagate": False,
        },
    }
}
```

#### 4. Example logs usage:

```python
import logging
logger = logging.getLogger(__name__)

logger.debug("debug message")
logger.info("info message")
logger.warning("warning message")
logger.error("error message")
logger.critical("critical message")
```