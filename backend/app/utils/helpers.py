import os
import hashlib
from datetime import datetime
from typing import Optional


def generate_file_hash(content: bytes) -> str:
    return hashlib.md5(content).hexdigest()


def get_file_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.1f} MB"


def parse_datetime(dt_string: str) -> Optional[datetime]:
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue

    return None
