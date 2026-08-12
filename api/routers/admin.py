from fastapi import APIRouter, Depends, HTTPException, status, Body
from typing import List, Dict, Any, Optional
from api.auth import verify_api_key
from database.db import (
    get_platform_stats,
    get_registration_by_code,
    approve_ticket_registration,
    reject_ticket_registration,
    get_ticket_by_id,
    get_all_registrations,
    get_tournaments_detailed,
    get_tournament_by_slug,
    create_tournament,
    update_tournament,
    delete_tournament,
    set_tournament_registration_status,
    log_admin_action,
    get_admin_audit_logs,
    generate_tournament_bracket,
    update_match_result,
    set_player_verification_status,
    set_team_verification_status
)

router = APIRouter(prefix="/api/admin", tags=["Admin Dashboard Endpoints"], dependencies=[Depends(verify_api_key)])

@router.post("/players/{player_id}/verify", summary="Verify or Suspend Player")
async def verify_player_api(player_id: int, payload: Dict[str, Any]):
    """Admin endpoint to set player verification status (VERIFIED, UNVERIFIED, SUSPENDED)."""
    status_val = payload.get("status", "VERIFIED")
    success = await set_player_verification_status(player_id, status_val)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player ID {player_id} not found.")
    await log_admin_action("API_ADMIN", "VERIFY_PLAYER", details=f"Set player #{player_id} status to {status_val}")
    return {"message": f"Player verification status set to {status_val}.", "player_id": player_id, "status": status_val}

@router.post("/teams/{team_id}/verify", summary="Verify or Suspend Team")
async def verify_team_api(team_id: int, payload: Dict[str, Any]):
    """Admin endpoint to set team verification status (VERIFIED, PENDING, UNVERIFIED, SUSPENDED)."""
    status_val = payload.get("status", "VERIFIED")
    success = await set_team_verification_status(team_id, status_val)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Team ID {team_id} not found.")
    await log_admin_action("API_ADMIN", "VERIFY_TEAM", details=f"Set team #{team_id} status to {status_val}")
    return {"message": f"Team verification status set to {status_val}.", "team_id": team_id, "status": status_val}

@router.get("/stats", response_model=Dict[str, Any], summary="Get Admin Dashboard Overview Metrics")
async def get_admin_stats():
    """Return platform metrics for the Admin Dashboard."""
    stats = await get_platform_stats()
    return stats

@router.get("/audit-logs", response_model=List[Dict[str, Any]], summary="Get System Audit Logs")
async def list_admin_audit_logs(limit: int = 50):
    """Fetch system audit log entries recorded during admin actions."""
    logs = await get_admin_audit_logs(limit)
    return logs

@router.get("/registrations", response_model=List[Dict[str, Any]], summary="Get All Registrations for Admin Review")
async def list_admin_registrations(status_filter: Optional[str] = None):
    """List team registrations with optional status filter (PENDING, APPROVED, REJECTED)."""
    registrations = await get_all_registrations(status_filter)
    return registrations

@router.post("/registrations/{ticket_id}/approve", summary="Approve Registration via API")
async def approve_registration_api(ticket_id: int):
    """Admin endpoint to approve a registration."""
    ticket = await get_ticket_by_id(ticket_id)
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
async def reject_registration_api(ticket_id: int, payload: Dict[str, Any] = Body(default={})):
    """Admin endpoint to reject a registration with reason."""
    reason = payload.get("reason", "Rejected by administrator.")
    ticket = await get_ticket_by_id(ticket_id)
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

@router.get("/tournaments", response_model=List[Dict[str, Any]], summary="Get All Tournaments for Admin")
async def list_admin_tournaments():
    """Return all detailed tournaments for admin panel."""
    tournaments = await get_tournaments_detailed()
    return tournaments

@router.get("/tournaments/{tournament_id}", summary="Get Single Tournament Details for Admin")
async def get_admin_single_tournament(tournament_id: str):
    """Fetch single tournament details by ID or slug."""
    tourn = await get_tournament_by_slug(tournament_id)
    if not tourn:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament {tournament_id} not found.")
    return tourn

@router.post("/tournaments", summary="Create New Tournament")
async def create_new_tournament_api(payload: Dict[str, Any]):
    """Create a new tournament dynamically in database."""
    if not payload.get("title"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tournament title is required.")
    try:
        new_tourn = await create_tournament(payload)
        t_id = new_tourn.get("tournament_id") if isinstance(new_tourn, dict) else None
        await log_admin_action("API_ADMIN", "CREATE_TOURNAMENT", t_id, f"Created tournament '{payload.get('title')}'")
        return {"message": "Tournament created successfully.", "tournament": new_tourn}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create tournament: {str(e)}")

@router.put("/tournaments/{tournament_id}", summary="Edit Tournament")
async def update_tournament_api(tournament_id: int, payload: Dict[str, Any]):
    """Edit existing tournament details in database."""
    try:
        updated = await update_tournament(tournament_id, payload)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament ID {tournament_id} not found.")
        await log_admin_action("API_ADMIN", "EDIT_TOURNAMENT", tournament_id, f"Updated tournament #{tournament_id}")
        return {"message": "Tournament updated successfully.", "tournament": updated}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update tournament: {str(e)}")

@router.delete("/tournaments/{tournament_id}", summary="Cancel Tournament")
async def delete_tournament_api(tournament_id: int):
    """Mark tournament status as CANCELLED."""
    success = await delete_tournament(tournament_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament ID {tournament_id} not found.")
    await log_admin_action("API_ADMIN", "CANCEL_TOURNAMENT", tournament_id, f"Cancelled tournament #{tournament_id}")
    return {"message": "Tournament cancelled successfully.", "tournament_id": tournament_id}

@router.post("/tournaments/{tournament_id}/open-registration", summary="Open Registration for Tournament")
async def open_tournament_registration_api(tournament_id: int):
    """Set registration status to OPEN."""
    success = await set_tournament_registration_status(tournament_id, "OPEN", "REGISTRATION_OPEN")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament ID {tournament_id} not found.")
    await log_admin_action("API_ADMIN", "OPEN_REGISTRATION", tournament_id, f"Opened registration for tournament #{tournament_id}")
    return {"message": "Tournament registration opened successfully.", "tournament_id": tournament_id, "registration_status": "OPEN"}

@router.post("/tournaments/{tournament_id}/close-registration", summary="Close Registration for Tournament")
async def close_tournament_registration_api(tournament_id: int):
    """Set registration status to CLOSED."""
    success = await set_tournament_registration_status(tournament_id, "CLOSED", "REGISTRATION_CLOSED")
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament ID {tournament_id} not found.")
    await log_admin_action("API_ADMIN", "CLOSE_REGISTRATION", tournament_id, f"Closed registration for tournament #{tournament_id}")
    return {"message": "Tournament registration closed successfully.", "tournament_id": tournament_id, "registration_status": "CLOSED"}

@router.post("/tournaments/{tournament_id}/status", summary="Change Tournament Main Status")
async def set_tournament_status_api(tournament_id: int, payload: Dict[str, Any]):
    """Set tournament status (DRAFT, REGISTRATION_OPEN, REGISTRATION_CLOSED, ONGOING, COMPLETED, CANCELLED)."""
    new_status = payload.get("status")
    if not new_status:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Status is required.")
    
    reg_status = "OPEN" if new_status == "REGISTRATION_OPEN" else ("CLOSED" if new_status in ["REGISTRATION_CLOSED", "ONGOING", "COMPLETED", "CANCELLED"] else "CLOSED")
    success = await set_tournament_registration_status(tournament_id, reg_status, new_status)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tournament ID {tournament_id} not found.")
    await log_admin_action("API_ADMIN", "CHANGE_STATUS", tournament_id, f"Changed status to '{new_status}' for tournament #{tournament_id}")
    return {"message": f"Tournament status changed to {new_status}.", "tournament_id": tournament_id, "status": new_status}

@router.post("/tournaments/{tournament_id}/generate-bracket", summary="Generate Tournament Bracket")
async def generate_bracket_api(tournament_id: str):
    """Generate elimination bracket from approved teams."""
    try:
        matches = await generate_tournament_bracket(tournament_id)
        return {"message": "Tournament bracket generated successfully.", "matches": matches}
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generating bracket: {str(e)}")

@router.post("/matches/{match_id}/result", summary="Submit Match Result")
async def submit_match_result_api(match_id: int, payload: Dict[str, Any]):
    """Record match score and auto-advance winner to next round."""
    team1_score = payload.get("team1_score", 0)
    team2_score = payload.get("team2_score", 0)
    winner_id = payload.get("winner_id")
    status_val = payload.get("status", "COMPLETED")

    match = await update_match_result(match_id, int(team1_score), int(team2_score), winner_id, status_val)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Match ID {match_id} not found.")

    return {"message": "Match result saved successfully.", "match": match}

