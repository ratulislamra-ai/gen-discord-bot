from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from api.auth import verify_api_key
from database.db import (
    get_all_tournaments,
    get_registration_by_code,
    get_approved_teams_by_tournament
)

router = APIRouter(prefix="/api", tags=["Website Integration API"])

@router.get("/health", summary="API Health Check")
async def health_check():
    """Public health check endpoint."""
    return {"status": "ok"}

@router.get("/tournaments", response_model=List[str], summary="List Available Tournaments")
async def list_tournaments(api_key: str = Depends(verify_api_key)):
    """Return available tournaments (Protected)."""
    try:
        tournaments = await get_all_tournaments()
        return tournaments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching tournaments: {str(e)}"
        )

@router.get("/registrations/{registration_id}", response_model=Dict[str, Any], summary="Get Registration Details")
async def get_registration_details(registration_id: str, api_key: str = Depends(verify_api_key)):
    """Return registration details by Registration ID (Protected). Sanitizes sensitive user data."""
    try:
        registration = await get_registration_by_code(registration_id)
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration with ID '{registration_id}' was not found."
            )
        return registration
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching registration details: {str(e)}"
        )

@router.get("/tournaments/{tournament_id}/approved-teams", response_model=List[Dict[str, Any]], summary="Get Approved Teams for Tournament")
async def get_tournament_approved_teams(tournament_id: str, api_key: str = Depends(verify_api_key)):
    """
    Return all APPROVED registrations for the specified tournament (Protected).
    Outputs sanitized team info for display on the GEN Esports website.
    Does NOT leak phone numbers, internal database IDs, or admin information.
    """
    try:
        approved_teams = await get_approved_teams_by_tournament(tournament_id)
        return approved_teams
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while fetching approved teams: {str(e)}"
        )
