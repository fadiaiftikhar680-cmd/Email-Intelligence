"""
Storage Abstraction for Uploads and Export Files.
Fulfills Part 4, Part 8.4, and Part 23.5.
"""
import os
import uuid
from django.conf import settings


def get_upload_dir() -> str:
    path = os.path.join(settings.MEDIA_ROOT, "uploads")
    os.makedirs(path, exist_ok=True)
    return path


def get_export_dir() -> str:
    path = os.path.join(settings.MEDIA_ROOT, "exports")
    os.makedirs(path, exist_ok=True)
    return path


def save_uploaded_file(file_obj, original_name: str) -> tuple[str, str]:
    """
    Saves an uploaded file with a randomized UUID filename.
    Returns (stored_relative_ref, full_absolute_path).
    """
    ext = os.path.splitext(original_name)[1].lower()
    random_filename = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(get_upload_dir(), random_filename)

    with open(full_path, "wb") as dest:
        for chunk in file_obj.chunks():
            dest.write(chunk)

    relative_ref = f"uploads/{random_filename}"
    return relative_ref, full_path


def save_export_file(content_bytes: bytes, original_name: str) -> tuple[str, str]:
    """
    Saves export content with a randomized UUID filename.
    Returns (stored_relative_ref, full_absolute_path).
    """
    ext = os.path.splitext(original_name)[1].lower()
    random_filename = f"{uuid.uuid4().hex}{ext}"
    full_path = os.path.join(get_export_dir(), random_filename)

    with open(full_path, "wb") as dest:
        dest.write(content_bytes)

    relative_ref = f"exports/{random_filename}"
    return relative_ref, full_path


def get_full_storage_path(relative_ref: str) -> str:
    return os.path.join(settings.MEDIA_ROOT, relative_ref.replace("/", os.sep))


def delete_stored_file(relative_ref: str) -> bool:
    full_path = get_full_storage_path(relative_ref)
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
            return True
        except Exception:
            return False
    return False

