from django.core.management.base import BaseCommand
import logging

class Command(BaseCommand):
    help = 'Generate some test logs'

    def handle(self, *args, **options):

        logger = logging.getLogger(__name__)
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")

        logger = logging.getLogger("other")
        logger.debug("debug message")
        logger.info("info message")
        logger.warning("warning message")
        logger.error("error message")
        logger.critical("critical message")
