"""Exception handling utilities for API endpoints."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from fastapi import HTTPException
from loguru import logger

from aln.app.schemas import StandardResponse
from fp.entity import FriendshipRequiredError


def exception_wrapper(
    error_message: str | None = None,
    catch_http_exc: bool = False,
) -> Callable:
    """Decorator to wrap endpoint exceptions into StandardResponse."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapped(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except HTTPException as e:
                if catch_http_exc:
                    logger.error(f"HTTP error in {func.__name__}: {e.detail}")
                    return StandardResponse(
                        success=False,
                        message=e.detail,
                        data={"error_code": e.status_code},
                    )
                else:
                    raise
            except FriendshipRequiredError as e:
                logger.warning(f"Friendship required in {func.__name__}: {e}")
                return StandardResponse(
                    success=False,
                    message=str(e),
                    data={"error_code": 400},
                )
            except Exception as e:
                logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
                if error_message is None:
                    message = str(e)
                else:
                    message = f"{error_message}: {str(e)}"
                return StandardResponse(
                    success=False,
                    message=message,
                    data={"error_code": 500},
                )

        return wrapped

    return decorator
