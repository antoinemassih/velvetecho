"""
VelvetEcho File Management System

World-class file upload, download, streaming, and management capabilities.

Features:
- Multi-backend storage (Local, S3, Azure, GCS)
- Chunked uploads for large files
- Streaming downloads with range requests
- File versioning and soft delete
- Image processing (thumbnails, resizing)
- Metadata extraction
- Virus scanning integration
- Access control and permissions
- CDN integration ready
"""

from velvetecho.files.models import File, Folder, FileVersion
from velvetecho.files.storage import StorageBackend, LocalStorage, S3Storage
from velvetecho.files.manager import FileManager
from velvetecho.files.upload import FileUploader, ChunkedUploader
from velvetecho.files.download import FileDownloader, StreamingDownloader

__all__ = [
    "File",
    "Folder",
    "FileVersion",
    "StorageBackend",
    "LocalStorage",
    "S3Storage",
    "FileManager",
    "FileUploader",
    "ChunkedUploader",
    "FileDownloader",
    "StreamingDownloader",
]
