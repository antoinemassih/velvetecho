"""
File Management Database Models

Models for files, folders, versions, and permissions.
"""

from uuid import uuid4
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, BigInteger, Text, Boolean, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from velvetecho.database import BaseModel, TimestampMixin, SoftDeleteMixin


class Folder(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    Folder for organizing files hierarchically

    Supports nested folders with parent_id relationship.
    """

    __tablename__ = "folders"

    name = Column(String(255), nullable=False)
    path = Column(String(1000), nullable=False, index=True)  # Full path for quick lookups
    parent_id = Column(PGUUID(as_uuid=True), ForeignKey("folders.id"), nullable=True)
    owner_id = Column(String(255), nullable=False, index=True)
    workspace_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)

    # Metadata
    description = Column(Text, nullable=True)
    color = Column(String(7), nullable=True)  # Hex color for UI
    icon = Column(String(50), nullable=True)  # Icon name for UI

    # Access control
    is_public = Column(Boolean, default=False)
    permissions = Column(JSON, nullable=True)  # {user_id: [read, write, delete], ...}

    # Relationships
    parent = relationship("Folder", remote_side="Folder.id", backref="children")
    files = relationship("File", back_populates="folder", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_folder_workspace_owner", "workspace_id", "owner_id"),
        Index("idx_folder_path", "path"),
    )


class File(BaseModel, TimestampMixin, SoftDeleteMixin):
    """
    File metadata and storage information

    Stores metadata about files while actual file content is in storage backend.
    Supports versioning, soft delete, and rich metadata.
    """

    __tablename__ = "files"

    # Basic metadata
    name = Column(String(255), nullable=False, index=True)
    original_name = Column(String(255), nullable=False)  # User's original filename
    mime_type = Column(String(100), nullable=False)
    size = Column(BigInteger, nullable=False)  # Bytes
    extension = Column(String(50), nullable=True)

    # Storage
    storage_backend = Column(String(50), nullable=False)  # local, s3, azure, gcs
    storage_path = Column(String(1000), nullable=False)  # Path in storage backend
    storage_bucket = Column(String(255), nullable=True)  # For cloud storage

    # Organization
    folder_id = Column(PGUUID(as_uuid=True), ForeignKey("folders.id"), nullable=True)
    owner_id = Column(String(255), nullable=False, index=True)
    workspace_id = Column(PGUUID(as_uuid=True), nullable=True, index=True)

    # File hashing (for deduplication and integrity)
    md5_hash = Column(String(32), nullable=True, index=True)
    sha256_hash = Column(String(64), nullable=True)

    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)

    # Thumbnails and previews
    has_thumbnail = Column(Boolean, default=False)
    thumbnail_path = Column(String(1000), nullable=True)
    has_preview = Column(Boolean, default=False)
    preview_path = Column(String(1000), nullable=True)

    # Media-specific metadata
    width = Column(Integer, nullable=True)  # For images/videos
    height = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # For videos/audio (seconds)

    # Access control
    is_public = Column(Boolean, default=False)
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime, nullable=True)

    # Virus scanning
    is_scanned = Column(Boolean, default=False)
    scan_status = Column(String(50), default="pending")  # pending, scanning, clean, infected
    scan_result = Column(JSON, nullable=True)

    # Metadata (EXIF, custom tags, etc.)
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)  # [tag1, tag2, ...]

    # Versioning
    version = Column(Integer, default=1)
    is_latest_version = Column(Boolean, default=True)
    previous_version_id = Column(PGUUID(as_uuid=True), ForeignKey("files.id"), nullable=True)

    # Relationships
    folder = relationship("Folder", back_populates="files")
    versions = relationship("FileVersion", back_populates="file", cascade="all, delete-orphan")
    previous_version = relationship("File", remote_side="File.id")

    __table_args__ = (
        Index("idx_file_workspace_owner", "workspace_id", "owner_id"),
        Index("idx_file_mime_type", "mime_type"),
        Index("idx_file_md5", "md5_hash"),
        Index("idx_file_name", "name"),
    )

    def to_dict(self):
        """Convert to dictionary with computed fields"""
        data = super().to_dict()
        data.update({
            "size_human": self._human_readable_size(self.size),
            "is_image": self.mime_type.startswith("image/") if self.mime_type else False,
            "is_video": self.mime_type.startswith("video/") if self.mime_type else False,
            "is_audio": self.mime_type.startswith("audio/") if self.mime_type else False,
            "is_document": self.mime_type in [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ] if self.mime_type else False,
        })
        return data

    @staticmethod
    def _human_readable_size(size_bytes: int) -> str:
        """Convert bytes to human-readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"


class FileVersion(BaseModel, TimestampMixin):
    """
    File version history

    Tracks all versions of a file for version control.
    """

    __tablename__ = "file_versions"

    file_id = Column(PGUUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    version = Column(Integer, nullable=False)

    # Storage (each version has its own storage path)
    storage_path = Column(String(1000), nullable=False)
    size = Column(BigInteger, nullable=False)
    md5_hash = Column(String(32), nullable=True)

    # Version metadata
    change_description = Column(Text, nullable=True)
    changed_by = Column(String(255), nullable=False)

    # Relationships
    file = relationship("File", back_populates="versions")

    __table_args__ = (
        Index("idx_file_version", "file_id", "version"),
    )


class FileShare(BaseModel, TimestampMixin):
    """
    File sharing and temporary access links

    Generate signed URLs for temporary file access.
    """

    __tablename__ = "file_shares"

    file_id = Column(PGUUID(as_uuid=True), ForeignKey("files.id"), nullable=False)
    share_token = Column(String(64), nullable=False, unique=True, index=True)

    # Access control
    shared_by = Column(String(255), nullable=False)
    shared_with = Column(String(255), nullable=True)  # Email or user ID, null = public

    # Permissions
    can_download = Column(Boolean, default=True)
    can_preview = Column(Boolean, default=True)
    can_edit = Column(Boolean, default=False)

    # Expiration
    expires_at = Column(DateTime, nullable=True)
    max_downloads = Column(Integer, nullable=True)
    download_count = Column(Integer, default=0)

    # Metadata
    message = Column(Text, nullable=True)
    password = Column(String(255), nullable=True)  # Hashed password for protected links

    __table_args__ = (
        Index("idx_share_token", "share_token"),
        Index("idx_share_expires", "expires_at"),
    )
