"""Dynamic filtering and sorting utilities"""

from typing import List, Optional, Any
from enum import Enum
from pydantic import BaseModel, Field


class FilterOperator(str, Enum):
    """Filter operators for dynamic queries"""

    EQ = "eq"  # Equal
    NE = "ne"  # Not equal
    GT = "gt"  # Greater than
    GTE = "gte"  # Greater than or equal
    LT = "lt"  # Less than
    LTE = "lte"  # Less than or equal
    LIKE = "like"  # Pattern matching
    IN = "in"  # In list
    IS_NULL = "is_null"  # Is NULL
    IS_NOT_NULL = "is_not_null"  # Is NOT NULL


class FilterCondition(BaseModel):
    """Single filter condition"""

    field: str
    operator: FilterOperator
    value: Optional[Any] = None


class FilterParams(BaseModel):
    """
    Filter parameters for dynamic queries.

    Example:
        filters = FilterParams(conditions=[
            FilterCondition(field="name", operator=FilterOperator.LIKE, value="%test%"),
            FilterCondition(field="status", operator=FilterOperator.EQ, value="active"),
        ])

        stmt = select(Workspace)
        stmt = apply_filters(stmt, Workspace, filters)
    """

    conditions: List[FilterCondition] = Field(default_factory=list)


class SortOrder(str, Enum):
    """Sort order"""

    ASC = "asc"
    DESC = "desc"


class SortField(BaseModel):
    """Single sort field"""

    field: str
    order: SortOrder = SortOrder.ASC


class SortParams(BaseModel):
    """
    Sort parameters for queries.

    Example:
        sort = SortParams(fields=[
            SortField(field="created_at", order=SortOrder.DESC),
            SortField(field="name", order=SortOrder.ASC),
        ])

        stmt = select(Workspace)
        stmt = apply_sorting(stmt, Workspace, sort)
    """

    fields: List[SortField] = Field(default_factory=list)


def apply_filters(stmt, model, filters: FilterParams):
    """
    Apply filters to a SQLAlchemy statement.

    Example:
        from sqlalchemy import select
        from velvetecho.database import apply_filters, FilterParams, FilterCondition, FilterOperator

        stmt = select(Workspace)
        filters = FilterParams(conditions=[
            FilterCondition(field="name", operator=FilterOperator.LIKE, value="%test%"),
            FilterCondition(field="status", operator=FilterOperator.IN, value=["active", "pending"]),
        ])
        stmt = apply_filters(stmt, Workspace, filters)

        result = await session.execute(stmt)
        workspaces = result.scalars().all()
    """
    for condition in filters.conditions:
        if not hasattr(model, condition.field):
            continue

        field = getattr(model, condition.field)

        if condition.operator == FilterOperator.EQ:
            stmt = stmt.where(field == condition.value)
        elif condition.operator == FilterOperator.NE:
            stmt = stmt.where(field != condition.value)
        elif condition.operator == FilterOperator.GT:
            stmt = stmt.where(field > condition.value)
        elif condition.operator == FilterOperator.GTE:
            stmt = stmt.where(field >= condition.value)
        elif condition.operator == FilterOperator.LT:
            stmt = stmt.where(field < condition.value)
        elif condition.operator == FilterOperator.LTE:
            stmt = stmt.where(field <= condition.value)
        elif condition.operator == FilterOperator.LIKE:
            stmt = stmt.where(field.like(condition.value))
        elif condition.operator == FilterOperator.IN:
            stmt = stmt.where(field.in_(condition.value))
        elif condition.operator == FilterOperator.IS_NULL:
            stmt = stmt.where(field.is_(None))
        elif condition.operator == FilterOperator.IS_NOT_NULL:
            stmt = stmt.where(field.isnot(None))

    return stmt


def apply_sorting(stmt, model, sort: SortParams):
    """
    Apply sorting to a SQLAlchemy statement.

    Example:
        from sqlalchemy import select
        from velvetecho.database import apply_sorting, SortParams, SortField, SortOrder

        stmt = select(Workspace)
        sort = SortParams(fields=[
            SortField(field="created_at", order=SortOrder.DESC),
            SortField(field="name", order=SortOrder.ASC),
        ])
        stmt = apply_sorting(stmt, Workspace, sort)

        result = await session.execute(stmt)
        workspaces = result.scalars().all()
    """
    for sort_field in sort.fields:
        if not hasattr(model, sort_field.field):
            continue

        field = getattr(model, sort_field.field)

        if sort_field.order == SortOrder.DESC:
            stmt = stmt.order_by(field.desc())
        else:
            stmt = stmt.order_by(field.asc())

    return stmt
