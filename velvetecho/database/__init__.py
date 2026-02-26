"""Database layer with SQLAlchemy ORM and Repository pattern"""

from velvetecho.database.base import BaseModel, Base
from velvetecho.database.repository import Repository
from velvetecho.database.connection import DatabaseConnection, get_session
from velvetecho.database.transactions import transaction
from velvetecho.database.mixins import TimestampMixin, SoftDeleteMixin, AuditMixin
from velvetecho.database.pagination import paginate, PaginationParams
from velvetecho.database.filtering import FilterParams, SortParams, apply_filters, apply_sorting

__all__ = [
    "BaseModel",
    "Base",
    "Repository",
    "DatabaseConnection",
    "get_session",
    "transaction",
    "TimestampMixin",
    "SoftDeleteMixin",
    "AuditMixin",
    "paginate",
    "PaginationParams",
    "FilterParams",
    "SortParams",
    "apply_filters",
    "apply_sorting",
]
