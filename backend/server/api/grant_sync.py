from fastapi import APIRouter, HTTPException, Query

from ..services.grant_sync import grant_sync_service

router = APIRouter(prefix="/jamai", tags=["jamai"])


@router.post("/sync-grants")
def sync_grants(limit: int = Query(20, ge=1, le=100)):
    """
    Trigger a JamAI sync from the scrap_result action table into the grants knowledge table.
    """
    try:
        summary = grant_sync_service.sync_pending_grants(limit=limit)
        return summary
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc

