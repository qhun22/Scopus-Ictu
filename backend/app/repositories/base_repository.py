"""Base repository — M0 scaffold.

Provides persistence boundary shared by all repositories.
CRUD logic is prohibited in M0.
"""

from __future__ import annotations

from typing import Generic, Sequence, TypeVar

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """M0 stub. TODO(M1): add generic get / list / add / update / delete."""

    def __init__(self, session, model: type[T]) -> None:
        self._session = session
        self._model = model

    # The signatures below are intentionally pass-only.
    # Real implementations belong to M1.

    def get(self, id: int) -> T | None:
        raise NotImplementedError("BaseRepository.get not implemented in M0.")

    def list(self, *, skip: int = 0, limit: int = 100) -> Sequence[T]:
        raise NotImplementedError("BaseRepository.list not implemented in M0.")

    def add(self, entity: T) -> T:
        raise NotImplementedError("BaseRepository.add not implemented in M0.")

    def update(self, entity: T) -> T:
        raise NotImplementedError("BaseRepository.update not implemented in M0.")

    def delete(self, entity: T) -> None:
        raise NotImplementedError("BaseRepository.delete not implemented in M0.")