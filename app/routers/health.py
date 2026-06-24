from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/api/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "app": "Proyecta360", "time": datetime.now(timezone.utc).isoformat()}
