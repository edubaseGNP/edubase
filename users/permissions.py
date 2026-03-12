"""
RBAC helpers for EduBase.

Usage in class-based views:
    class MyView(RoleRequiredMixin, View):
        required_roles = [User.Role.TEACHER, User.Role.ADMIN]

Usage in function-based views:
    @role_required(User.Role.TEACHER, User.Role.ADMIN)
    def my_view(request): ...
"""

from functools import wraps

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import User


class RoleRequiredMixin(LoginRequiredMixin):
    """Restrict access to views by user role."""

    required_roles: list[str] = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if self.required_roles:
            if not (
                request.user.role in self.required_roles
                or request.user.is_superuser
            ):
                raise PermissionDenied

        return super().dispatch(request, *args, **kwargs)


def role_required(*roles: str):
    """Decorator for function-based views."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('account_login')
            if roles and not (
                request.user.role in roles or request.user.is_superuser
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# Convenience shortcuts
teacher_required = role_required(User.Role.TEACHER, User.Role.ADMIN)
admin_required = role_required(User.Role.ADMIN)
