"""
Auto-Login Middleware for Direct Access.
Automatically authenticates all requests as the primary administrator,
completely removing the login and sign-in requirements.
"""
from django.contrib.auth import get_user_model


class AutoLoginMiddleware:
    """
    Bypasses authentication prompts by automatically binding the primary admin user
    to request.user on every incoming HTTP request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            User = get_user_model()
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.filter(email="admin@emailintelligence.local").first()
            if not user:
                user = User.objects.first()
            if not user:
                user = User.objects.create_superuser(
                    email="admin@emailintelligence.local",
                    password="AdminPassword123#Secure"
                )
            request.user = user

        return self.get_response(request)

