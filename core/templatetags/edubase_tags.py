"""Custom template tags and filters for EduBase."""

from django import template

register = template.Library()


@register.filter(name='can_upload_to')
def can_upload_to(user, subject):
    """Usage: {% if request.user|can_upload_to:subject %}"""
    return user.can_upload_to(subject)
