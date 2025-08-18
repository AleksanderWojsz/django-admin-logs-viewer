from django.conf import settings
from .defaults import DEFAULTS

class AppSettings:
    def __getattr__(self, name):
        if hasattr(settings, name):
            return getattr(settings, name)
        return DEFAULTS.get(name)

app_settings = AppSettings()
