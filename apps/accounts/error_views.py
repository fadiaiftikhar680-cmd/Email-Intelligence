"""
Custom user-safe error views.
Fulfills Part 10 (S-23) and Part 15.
"""
from django.shortcuts import render


def handler400(request, exception=None):
    return render(request, "errors/400.html", {"error_code": "BAD_REQUEST", "message": "The request could not be processed due to invalid syntax."}, status=400)


def handler403(request, exception=None):
    return render(request, "errors/403.html", {"error_code": "FORBIDDEN", "message": "You do not have permission to access this resource."}, status=403)


def handler404(request, exception=None):
    return render(request, "errors/404.html", {"error_code": "NOT_FOUND", "message": "The requested page or record could not be found."}, status=404)


def handler500(request):
    return render(request, "errors/500.html", {"error_code": "INTERNAL_SERVER_ERROR", "message": "An unexpected error occurred. The support team has been notified."}, status=500)

