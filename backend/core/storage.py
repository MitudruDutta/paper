"""File storage management for documents."""

import logging
import uuid
import aiofiles
import aiofiles.os
from pathlib import Path

from fastapi import UploadFile

from core.config import settings

logger = logging.getLogger(__name__)


async def ensure_storage_dir_exists() -> None:
    """Create storage directory if it doesn't exist."""
    storage_path = Path(settings.document_storage_path)
    if not await aiofiles.os.path.exists(storage_path):
        await aiofiles.os.makedirs(storage_path, exist_ok=True)
        logger.info(f"Created storage directory: {storage_path}")


def generate_stored_filename(document_id: uuid.UUID, extension: str = "pdf") -> str:
    """
    Generate a safe stored filename from document ID.
    
    Args:
        document_id: UUID of the document
        extension: File extension without leading dot (default: "pdf")
    
    Returns:
        Filename in format "{document_id}.{extension}"
    
    Raises:
        ValueError: If extension is empty, too long, or contains invalid characters
    """
    import re
    
    # Normalize: strip whitespace, leading dots, and lowercase
    ext = extension.strip().lstrip(".").lower()
    
    if not ext:
        raise ValueError("Extension cannot be empty")
    
    if len(ext) > 10:
        raise ValueError(f"Extension too long (max 10 chars): {ext}")
    
    # Whitelist: only ASCII letters, digits, hyphen, underscore
    if not re.match(r'^[a-z0-9_-]+$', ext):
        raise ValueError(f"Extension contains invalid characters: {extension}")
    
    return f"{document_id}.{ext}"


def get_file_path(stored_filename: str) -> Path:
    """
    Get full path for a stored file.
    
    Raises:
        ValueError: If stored_filename contains path traversal attempts
    """
    # Sanitize: use only the filename component, reject traversal attempts
    safe_name = Path(stored_filename).name
    if safe_name != stored_filename or ".." in stored_filename:
        raise ValueError(f"Invalid stored filename: {stored_filename}")
    
    storage_base = Path(settings.document_storage_path).resolve()
    file_path = (storage_base / safe_name).resolve()
    
    # Ensure the resolved path is within the storage directory (Python 3.9+)
    if not file_path.is_relative_to(storage_base):
        raise ValueError(f"Path traversal detected: {stored_filename}")
    
    return file_path


async def save_uploaded_file(
    temp_path: Path,
    document_id: uuid.UUID,
    extension: str = "pdf",
) -> tuple[str, Path]:
    """
    Move validated file from temp location to permanent storage.
    
    Args:
        temp_path: Path to the temporary file
        document_id: UUID of the document
        extension: File extension without leading dot (default: "pdf")
    
    Returns:
        Tuple of (stored_filename, file_path)
    """
    await ensure_storage_dir_exists()
    
    stored_filename = generate_stored_filename(document_id, extension)
    file_path = get_file_path(stored_filename)
    
    try:
        await aiofiles.os.rename(str(temp_path), str(file_path))
        logger.info(f"Stored document {document_id} at {file_path}")
        return stored_filename, file_path
    except OSError:
        # Cross-device move - copy then delete using context managers
        try:
            async with aiofiles.open(temp_path, "rb") as src:
                async with aiofiles.open(file_path, "wb") as dst:
                    while chunk := await src.read(8192):
                        await dst.write(chunk)
            # Only remove temp after successful copy
            await aiofiles.os.remove(temp_path)
            logger.info(f"Stored document {document_id} at {file_path} (copied)")
            return stored_filename, file_path
        except Exception as e:
            logger.error(f"Failed to copy file to {file_path}: {e}")
            # Remove partial destination file if it exists
            if await aiofiles.os.path.exists(file_path):
                try:
                    await aiofiles.os.remove(file_path)
                    logger.info(f"Cleaned up partial file: {file_path}")
                except Exception as cleanup_err:
                    logger.warning(f"Failed to clean up partial file {file_path}: {cleanup_err}")
            raise


async def delete_file(stored_filename: str) -> bool:
    """
    Delete a stored file.
    
    Returns:
        True if deleted, False if file didn't exist
    """
    file_path = get_file_path(stored_filename)
    try:
        if await aiofiles.os.path.exists(file_path):
            await aiofiles.os.remove(file_path)
            logger.info(f"Deleted file: {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to delete file {file_path}: {e}")
        raise


async def save_temp_file(upload_file: UploadFile, max_size: int, suffix: str = ".tmp") -> Path:
    """
    Save upload file content to a temporary file using streaming.
    
    Raises:
        ValueError: If file size exceeds max_size
    """
    temp_dir = Path(settings.document_storage_path) / "temp"
    await aiofiles.os.makedirs(temp_dir, exist_ok=True)
    
    temp_filename = f"{uuid.uuid4()}{suffix}"
    temp_path = temp_dir / temp_filename
    
    file_size = 0
    
    try:
        async with aiofiles.open(temp_path, "wb") as f:
            while chunk := await upload_file.read(8192):
                file_size += len(chunk)
                if file_size > max_size:
                    raise ValueError(f"File size exceeds maximum limit of {max_size} bytes")
                await f.write(chunk)
    except Exception:
        # Clean up partial file on error
        await delete_temp_file(temp_path)
        raise
    
    return temp_path


async def delete_temp_file(temp_path: Path) -> None:
    """Delete a temporary file, ignoring errors."""
    try:
        if await aiofiles.os.path.exists(temp_path):
            await aiofiles.os.remove(temp_path)
    except Exception as e:
        logger.warning(f"Failed to delete temp file {temp_path}: {e}")
