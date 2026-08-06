from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int

    @classmethod
    def build(cls, items, total: int, limit: int, offset: int) -> "Page[T]":
        return cls(items=list(items), total=int(total), limit=int(limit), offset=int(offset))
