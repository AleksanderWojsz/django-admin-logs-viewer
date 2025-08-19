from django.contrib.auth.signals import user_logged_in
import logging

logger = logging.getLogger(__name__)

# If user just logged in, we want his previous log in datetime, so we need to read it before it is overwritten
def store_previous_login(sender, request, user, **kwargs):
    if user.last_login:
        request.session['previous_login'] = user.last_login.isoformat()

user_logged_in.connect(store_previous_login)
