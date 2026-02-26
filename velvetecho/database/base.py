"""Base model classes for SQLAlchemy"""

from datetime import datetime
from uuid import UUID, uuid4
from typing import Any, Dict
from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.declarative import declared_attr, declarative_base
from sqlalchemy.orm import DeclarativeMeta

Base = declarative_base()


class BaseModel(Base):
    """
    Base model with common fields and utilities.

    All models should inherit from this.

    Example:
        class Workspace(BaseModel):
            __tablename__ = "workspaces"

            name = Column(String, nullable=False)
            description = Column(String)
    """

    __abstract__ = True

    @declared_attr
    def id(cls):
        """Primary key (UUID)"""
        return Column(
            PGUUID(as_uuid=True),
            primary_key=True,
            default=uuid4,
            nullable=False,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }

    def update(self, **kwargs: Any) -> None:
        """Update model attributes"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__}(id={self.id})>"
