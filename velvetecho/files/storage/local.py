"""
Local Filesystem Storage Backend

Store files on local disk with proper organization.
"""

import os
import shutil
import hashlib
from pathlib import Path
from typing import BinaryIO, Optional, AsyncIterator
from datetime import datetime

from velvetecho.files.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    """
    Local filesystem storage backend

    Stores files in a local directory with date-based organization:
    - base_path/2026/03/01/uuid.ext
    """

    def __init__(self, base_path: str = "./storage"):
        """
        Initialize local storage

        Args:
            base_path: Base directory for file storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_date_path(self) -> Path:
        """Get date-based subdirectory (YYYY/MM/DD)"""
        now = datetime.utcnow()
        return self.base_path / str(now.year) / f"{now.month:02d}" / f"{now.day:02d}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve storage path to absolute path"""
        return self.base_path / path

    async def save(
        self,
        file_data: BinaryIO,
        path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """Save file to local storage"""
        # Create directory structure
        file_path = self._resolve_path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        with open(file_path, "wb") as f:
            if hasattr(file_data, "read"):
                shutil.copyfileobj(file_data, f)
            else:
                f.write(file_data)

        return path

    async def read(self, path: str) -> bytes:
        """Read file from local storage"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(file_path, "rb") as f:
            return f.read()

    async def stream(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """Stream file from local storage"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def delete(self, path: str) -> bool:
        """Delete file from local storage"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            return False

        file_path.unlink()

        # Clean up empty directories
        try:
            file_path.parent.rmdir()
        except OSError:
            pass  # Directory not empty

        return True

    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        return self._resolve_path(path).exists()

    async def get_size(self, path: str) -> int:
        """Get file size"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return file_path.stat().st_size

    async def get_url(
        self,
        path: str,
        expires_in: Optional[int] = None,
        response_headers: Optional[dict] = None,
    ) -> str:
        """
        Get URL for local file

        Note: For local storage, this returns a relative path.
        In production, you'd typically serve files through a web server
        or CDN with proper access control.
        """
        # In production, this would return a signed URL from your web server
        # For now, return the storage path (you'd map this to /api/files/download/{path})
        return f"/api/files/download/{path}"

    async def copy(self, source_path: str, dest_path: str) -> bool:
        """Copy file"""
        source = self._resolve_path(source_path)
        dest = self._resolve_path(dest_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)

        return True

    async def move(self, source_path: str, dest_path: str) -> bool:
        """Move file"""
        source = self._resolve_path(source_path)
        dest = self._resolve_path(dest_path)

        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))

        return True

    async def list_files(
        self,
        prefix: Optional[str] = None,
        recursive: bool = False,
    ) -> list[dict]:
        """List files in directory"""
        base_path = self._resolve_path(prefix) if prefix else self.base_path

        if not base_path.exists():
            return []

        files = []
        pattern = "**/*" if recursive else "*"

        for file_path in base_path.glob(pattern):
            if file_path.is_file():
                rel_path = file_path.relative_to(self.base_path)
                stat = file_path.stat()

                files.append({
                    "path": str(rel_path),
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                })

        return files

    async def calculate_md5(self, path: str) -> str:
        """Calculate MD5 hash of file"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5_hash.update(chunk)

        return md5_hash.hexdigest()

    async def calculate_sha256(self, path: str) -> str:
        """Calculate SHA256 hash of file"""
        file_path = self._resolve_path(path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        sha256_hash = hashlib.sha256()

        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256_hash.update(chunk)

        return sha256_hash.hexdigest()
