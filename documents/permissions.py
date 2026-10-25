from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def can_manage_documents(user):
    """Only active staff users (is_staff ticked in the admin) may manage documents."""
    return bool(user.is_authenticated and user.is_active and user.is_staff)


def document_manager_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not can_manage_documents(request.user):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapper
