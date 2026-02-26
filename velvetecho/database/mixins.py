"""Reusable model mixins"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Column, DateTime, String
from sqlalchemy.ext.declarative import declared_attr


class TimestampMixin:
    """
    Adds created_at and updated_at timestamps.

    Example:
        class Workspace(BaseModel, TimestampMixin):
            __tablename__ = "workspaces"
            name = Column(String)
    """

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=datetime.utcnow, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime,
            default=datetime.utcnow,
            onupdate=datetime.utcnow,
            nullable=False,
        )


class SoftDeleteMixin:
    """
    Adds soft delete support (deleted_at timestamp).

    Example:
        class Workspace(BaseModel, SoftDeleteMixin):
            __tablename__ = "workspaces"

        # Soft delete
        workspace.deleted_at = datetime.utcnow()

        # Check if deleted
        if workspace.is_deleted:
            ...
    """

    @declared_attr
    def deleted_at(cls):
        return Column(DateTime, nullable=True)

    @property
    def is_deleted(self) -> bool:
        """Check if model is soft-deleted"""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Soft delete this model"""
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        """Restore soft-deleted model"""
        self.deleted_at = None


class AuditMixin:
    """
    Adds audit fields (created_by, updated_by).

    Example:
        class Workspace(BaseModel, AuditMixin):
            __tablename__ = "workspaces"

        workspace.created_by = current_user_id
        workspace.updated_by = current_user_id
    """

    @declared_attr
    def created_by(cls):
        return Column(String, nullable=True)

    @declared_attr
    def updated_by(cls):
        return Column(String, nullable=True)
