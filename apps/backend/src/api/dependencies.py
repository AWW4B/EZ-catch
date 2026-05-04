from __future__ import annotations

from sqlalchemy.orm import Session

from src.models.database import get_db  # noqa: F401  re-exported as convenience


def get_db_dep():
    """
    Re-exports ``get_db`` so routes can import from a single location:

        from src.api.dependencies import get_db_dep
        ...
        db: Session = Depends(get_db_dep)
    """
    yield from get_db()
