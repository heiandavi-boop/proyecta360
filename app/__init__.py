"""Backend package. Re-exports the FastAPI instance so ``uvicorn app:app``
keeps working after the split from the old single-file app.py."""
from app.main import app

__all__ = ["app"]
