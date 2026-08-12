import os
import time
from typing import Tuple

# Directory where logos are saved locally
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "logos")
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

def ensure_upload_dir_exists():
    """Ensure the uploads/logos directory exists."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_logo_file(filename: str, size_bytes: int, content_type: str = "") -> Tuple[bool, str]:
    """
    Validate logo file parameters.
    Returns (is_valid, error_message).
    """
    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"File size ({size_mb:.2f} MB) exceeds the maximum allowed limit of 5 MB."

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return False, f"Invalid file format '{ext}'. Only {allowed_str} images are allowed."

    if content_type and not content_type.startswith("image/"):
        return False, f"Invalid content type '{content_type}'. Must be an image file."

    return True, ""

def save_team_logo(file_bytes: bytes, original_filename: str, ticket_id: int) -> Tuple[str, str]:
    """
    Save raw logo bytes to persistent storage.
    Returns (local_file_path, relative_url_path).
    Modular design allows replacing local disk storage with cloud storage (Cloudinary, AWS S3) in the future.
    """
    is_valid, err_msg = validate_logo_file(original_filename, len(file_bytes))
    if not is_valid:
        raise ValueError(err_msg)

    ensure_upload_dir_exists()

    ext = os.path.splitext(original_filename)[1].lower()
    timestamp = int(time.time())
    save_filename = f"logo_ticket_{ticket_id}_{timestamp}{ext}"
    local_path = os.path.join(UPLOAD_DIR, save_filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    relative_path = f"uploads/logos/{save_filename}"
    return local_path, relative_path
