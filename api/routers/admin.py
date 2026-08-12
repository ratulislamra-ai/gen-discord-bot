from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from api.auth import verify_api_key
from database.db import (
    get_platform_stats,
    get_registration_by_code,
    approve_ticket_registration,
    reject_ticket_registration,
    get_ticket_by_id
)

router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard Endpoints"], dependencies=[Depends(verify_api_key)])

@router.get("/stats", response_model=Dict[str, Any], summary="Get Admin Dashboard Overview Metrics")
async def get_admin_stats():
    """Return platform metrics for the Admin Dashboard."""
    stats = await get_platform_stats()
    return stats

@router.post("/registrations/{ticket_id}/approve", summary="Approve Registration via API")
async def approve_registration_api(ticket_id: int):
    """Admin endpoint to approve a registration."""
    ticket = await get_ticket_id_record(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registration with Ticket ID {ticket_id} was not found."
        )

    if ticket["status"] != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration is currently in status '{ticket['status']}' and cannot be approved."
        )

    success = await approve_ticket_registration(ticket_id, "API_ADMIN")
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update registration status in database."
        )

    return {"message": "Registration approved successfully.", "ticket_id": ticket_id, "status": "APPROVED"}

@router.post("/registrations/{ticket_id}/reject", summary="Reject Registration via API")
async def reject_registration_api(ticket_id: int, reason: str = "Rejected by administrator."):
    """Admin endpoint to reject a registration with reason."""
    ticket = await get_ticket_id_record(ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Registration with Ticket ID {ticket_id} was not found."
        )

    if ticket["status"] != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Registration is currently in status '{ticket['status']}' and cannot be rejected."
        )

    success = await reject_ticket_registration(ticket_id, "API_ADMIN", reason)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update registration status in database."
        )

    return {"message": "Registration rejected successfully.", "ticket_id": ticket_id, "status": "REJECTED", "reason": reason}

async def get_ticket_id_record(ticket_id: int):
    return await get_ticket_by_id(ticket_id)
