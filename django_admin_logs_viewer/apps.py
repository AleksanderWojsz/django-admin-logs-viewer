from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class DjangoAdminLogsViewerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_admin_logs_viewer"

    def ready(self):
        import django_admin_logs_viewer.signals
