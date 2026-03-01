"""
Storage Backend Abstraction

Multi-backend storage system supporting local, S3, Azure, and GCS.
"""

from velvetecho.files.storage.base import StorageBackend
from velvetecho.files.storage.local import LocalStorage
from velvetecho.files.storage.s3 import S3Storage

__all__ = ["StorageBackend", "LocalStorage", "S3Storage"]
