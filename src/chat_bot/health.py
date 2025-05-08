
from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def health_check():
    """Health check endpoint for Railway."""
    return {"status": "ok", "service": "chat"}
