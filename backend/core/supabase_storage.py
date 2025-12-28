"""Supabase Storage client for PDF storage."""

import logging
from pathlib import Path

import aiofiles
import httpx

from core.config import settings

logger = logging.getLogger(__name__)

CHUNK_SIZE = 65536  # 64KB chunks


def is_supabase_storage_configured() -> bool:
    """Check if Supabase Storage is configured."""
    return bool(settings.supabase_storage_url and settings.supabase_service_role_key)


def _get_headers() -> dict:
    """Get auth headers for Supabase Storage API."""
    return {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }


def _get_storage_url(path: str) -> str:
    """Build full storage URL."""
    base = settings.supabase_storage_url.rstrip("/")
    return f"{base}/object/{settings.supabase_storage_bucket}/{path}"


async def upload_to_supabase(file_path: Path, stored_filename: str) -> bool:
    """
    Upload file to Supabase Storage using streaming.
    
    Returns True on success, raises on failure.
    """
    url = _get_storage_url(stored_filename)
    
    # Read file content asynchronously
    async with aiofiles.open(file_path, "rb") as f:
        content = await f.read()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            url,
            headers={**_get_headers(), "Content-Type": "application/pdf"},
            content=content,
        )
        
        if response.status_code in (200, 201):
            logger.info(f"Uploaded {stored_filename} to Supabase Storage")
            return True
        
        # Handle duplicate - try upsert
        if response.status_code == 400 and "Duplicate" in response.text:
            response = await client.put(
                url,
                headers={**_get_headers(), "Content-Type": "application/pdf"},
                content=content,
            )
            if response.status_code in (200, 201):
                logger.info(f"Updated {stored_filename} in Supabase Storage")
                return True
        
        logger.error(f"Supabase upload failed: {response.status_code} {response.text}")
        raise RuntimeError(f"Failed to upload to Supabase: {response.status_code}")


async def download_from_supabase(stored_filename: str, dest_path: Path) -> bool:
    """
    Download file from Supabase Storage to local path using streaming.
    
    Returns True on success.
    """
    url = _get_storage_url(stored_filename)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        async with client.stream("GET", url, headers=_get_headers()) as response:
            if response.status_code == 200:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                async with aiofiles.open(dest_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=CHUNK_SIZE):
                        await f.write(chunk)
                logger.info(f"Downloaded {stored_filename} from Supabase Storage")
                return True
            
            if response.status_code == 404:
                logger.warning(f"File not found in Supabase: {stored_filename}")
                return False
            
            logger.error(f"Supabase download failed: {response.status_code}")
            raise RuntimeError(f"Failed to download from Supabase: {response.status_code}")


async def delete_from_supabase(stored_filename: str) -> bool:
    """Delete file from Supabase Storage."""
    base = settings.supabase_storage_url.rstrip("/")
    url = f"{base}/object/{settings.supabase_storage_bucket}"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            "DELETE",
            url,
            headers=_get_headers(),
            json={"prefixes": [stored_filename]},
        )
        
        if response.status_code in (200, 204):
            logger.info(f"Deleted {stored_filename} from Supabase Storage")
            return True
        
        logger.warning(f"Supabase delete returned: {response.status_code}")
        return False


def get_signed_url(stored_filename: str, expires_in: int = 3600) -> str:
    """
    Generate a signed URL for temporary access.
    
    Note: This is synchronous for use in response building.
    For private buckets, use this to serve PDFs.
    """
    base = settings.supabase_storage_url.rstrip("/")
    return f"{base}/object/sign/{settings.supabase_storage_bucket}/{stored_filename}?expiresIn={expires_in}"
