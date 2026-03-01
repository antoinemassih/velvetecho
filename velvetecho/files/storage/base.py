"""
Storage Backend Base Class

Abstract interface for file storage backends.
"""

from abc import ABC, abstractmethod
from typing import BinaryIO, Optional, AsyncIterator
from pathlib import Path


class StorageBackend(ABC):
    """
    Abstract base class for storage backends

    All storage backends must implement these methods.
    """

    @abstractmethod
    async def save(
        self,
        file_data: BinaryIO,
        path: str,
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Save file to storage

        Args:
            file_data: File binary data
            path: Storage path
            content_type: MIME type
            metadata: Additional metadata

        Returns:
            Final storage path
        """
        pass

    @abstractmethod
    async def read(self, path: str) -> bytes:
        """
        Read file from storage

        Args:
            path: Storage path

        Returns:
            File binary data
        """
        pass

    @abstractmethod
    async def stream(self, path: str, chunk_size: int = 8192) -> AsyncIterator[bytes]:
        """
        Stream file from storage in chunks

        Args:
            path: Storage path
            chunk_size: Chunk size in bytes

        Yields:
            File chunks
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete file from storage

        Args:
            path: Storage path

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if file exists

        Args:
            path: Storage path

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    async def get_size(self, path: str) -> int:
        """
        Get file size in bytes

        Args:
            path: Storage path

        Returns:
            File size in bytes
        """
        pass

    @abstractmethod
    async def get_url(
        self,
        path: str,
        expires_in: Optional[int] = None,
        response_headers: Optional[dict] = None,
    ) -> str:
        """
        Get temporary signed URL for file access

        Args:
            path: Storage path
            expires_in: Expiration time in seconds (None = permanent)
            response_headers: Headers to include in response

        Returns:
            Signed URL
        """
        pass

    @abstractmethod
    async def copy(self, source_path: str, dest_path: str) -> bool:
        """
        Copy file within storage

        Args:
            source_path: Source path
            dest_path: Destination path

        Returns:
            True if copied successfully
        """
        pass

    @abstractmethod
    async def move(self, source_path: str, dest_path: str) -> bool:
        """
        Move file within storage

        Args:
            source_path: Source path
            dest_path: Destination path

        Returns:
            True if moved successfully
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        prefix: Optional[str] = None,
        recursive: bool = False,
    ) -> list[dict]:
        """
        List files in storage

        Args:
            prefix: Path prefix to filter
            recursive: Include subdirectories

        Returns:
            List of file metadata dicts
        """
        pass
