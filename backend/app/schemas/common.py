from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, List

T = TypeVar('T')


class PaginationParams(BaseModel):
    page: int = 1
    page_size: int = 20


class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: List[T] = []
    meta: dict = {"page": 1, "page_size": 20, "total": 0}


class ApiResponse(BaseModel, Generic[T]):
    code: int = 200
    message: str = "success"
    data: Optional[T] = None


class ErrorResponse(BaseModel):
    code: int = 400
    message: str
    details: Optional[dict] = None
