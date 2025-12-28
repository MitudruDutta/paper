"""File storage management for documents."""

import logging
import uuid
import aiofiles
import aiofiles.os
from pathlib import Path

from fastapi import UploadFile

from core.config import settings
from core.supabase_storage import (
    is_supabase_storage_configured,
    upload_to_supabase,
    download_from_supabase,
    delete_from_supabase,
)

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
    Save file to storage (Supabase in production, local in dev).
    
    Returns:
        Tuple of (stored_filename, local_file_path)
    """
    stored_filename = generate_stored_filename(document_id, extension)
    
    if is_supabase_storage_configured():
        # Upload to Supabase Storage
        await upload_to_supabase(temp_path, stored_filename)
        # Keep local copy for processing
        await ensure_storage_dir_exists()
        file_path = get_file_path(stored_filename)
        await aiofiles.os.rename(str(temp_path), str(file_path))
        logger.info(f"Stored {document_id} in Supabase + local cache")
        return stored_filename, file_path
    
    # Local storage only
    await ensure_storage_dir_exists()
    file_path = get_file_path(stored_filename)
    
    try:
        await aiofiles.os.rename(str(temp_path), str(file_path))
        logger.info(f"Stored document {document_id} at {file_path}")
        return stored_filename, file_path
    except OSError:
        # Cross-device move - copy then delete
        async with aiofiles.open(temp_path, "rb") as src:
            async with aiofiles.open(file_path, "wb") as dst:
                while chunk := await src.read(8192):
                    await dst.write(chunk)
        await aiofiles.os.remove(temp_path)
        logger.info(f"Stored document {document_id} at {file_path} (copied)")
        return stored_filename, file_path


async def get_file_for_processing(stored_filename: str) -> Path:
    """
    Get file path for processing, downloading from Supabase if needed.
    
    Returns local path to the file.
    """
    file_path = get_file_path(stored_filename)
    
    # Check if local copy exists
    if await aiofiles.os.path.exists(file_path):
        return file_path
    
    # Download from Supabase if configured
    if is_supabase_storage_configured():
        await ensure_storage_dir_exists()
        success = await download_from_supabase(stored_filename, file_path)
        if success:
            return file_path
        raise FileNotFoundError(f"File not found in Supabase: {stored_filename}")
    
    raise FileNotFoundError(f"File not found: {stored_filename}")


async def delete_file(stored_filename: str) -> bool:
    """
    Delete a stored file from all storage locations.
    
    Returns:
        True if deleted, False if file didn't exist
    """
    deleted = False
    
    # Delete from Supabase if configured
    if is_supabase_storage_configured():
        try:
            await delete_from_supabase(stored_filename)
            deleted = True
        except Exception as e:
            logger.warning(f"Failed to delete from Supabase: {e}")
    
    # Delete local copy
    file_path = get_file_path(stored_filename)
    try:
        if await aiofiles.os.path.exists(file_path):
            await aiofiles.os.remove(file_path)
            logger.info(f"Deleted local file: {file_path}")
            deleted = True
    except Exception as e:
        logger.error(f"Failed to delete local file {file_path}: {e}")
    
    return deleted


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
