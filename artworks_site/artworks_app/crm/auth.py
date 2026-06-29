from functools import wraps

from flask import abort, current_app
from flask_login import current_user, login_required


def is_staff_user(user):
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'is_staff', False):
        return True
    admin_emails = current_app.config.get('ADMIN_EMAILS') or []
    return (user.email or '').lower() in admin_emails


def staff_required(f):
    @login_required
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not is_staff_user(current_user):
            abort(403)
        return f(*args, **kwargs)
    return wrapped
