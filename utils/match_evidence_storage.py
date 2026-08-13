import os
import time
import uuid
from typing import Tuple

# Directory where match result evidence screenshots are saved locally
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads", "match-evidence")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}

def ensure_evidence_upload_dir_exists():
    """Ensure the uploads/match-evidence directory exists."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)

def validate_evidence_file(filename: str, size_bytes: int, content_type: str = "") -> Tuple[bool, str]:
    """
    Validate match result screenshot evidence parameters.
    Returns (is_valid, error_message).
    """
    if size_bytes > MAX_FILE_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return False, f"File size ({size_mb:.2f} MB) exceeds the maximum allowed limit of 10 MB."

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        return False, f"Invalid file format '{ext}'. Only {allowed_str} images are allowed."

    if content_type and not content_type.startswith("image/"):
        return False, f"Invalid content type '{content_type}'. Must be a valid image file."

    return True, ""

def save_match_evidence(file_bytes: bytes, original_filename: str, match_id: int | None = None) -> Tuple[str, str]:
    """
    Save raw screenshot evidence bytes to persistent storage with a safe UUID filename.
    Returns (local_file_path, relative_url_path).
    """
    is_valid, err_msg = validate_evidence_file(original_filename, len(file_bytes))
    if not is_valid:
        raise ValueError(err_msg)

    ensure_evidence_upload_dir_exists()

    ext = os.path.splitext(original_filename)[1].lower()
    timestamp = int(time.time())
    unique_id = uuid.uuid4().hex[:8]
    
    match_tag = f"match_{match_id}" if match_id else "match_result"
    save_filename = f"{match_tag}_{unique_id}_{timestamp}{ext}"
    local_path = os.path.join(UPLOAD_DIR, save_filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    relative_url = f"/uploads/match-evidence/{save_filename}"
    return local_path, relative_url
