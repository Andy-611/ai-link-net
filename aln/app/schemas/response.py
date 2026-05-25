"""HTTP response envelope schemas for app layer."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic.generics import GenericModel

T = TypeVar("T")


class StandardResponse(GenericModel, Generic[T]):
    """Standard HTTP response envelope for app APIs."""

    success: bool
    message: str
    data: T
