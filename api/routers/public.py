from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import config.settings as settings
from database.db import (
    get_tournaments_detailed,
    get_tournament_by_slug,
    get_approved_teams_by_tournament,
    get_platform_stats,
    get_public_matches
)

router = APIRouter(prefix="/api/public", tags=["Public Website Endpoints"])

@router.get("/config", response_model=Dict[str, Any], summary="Get Public App Config")
async def get_public_config():
    """Return public platform configuration (e.g. Discord invite URL)."""
    return {
        "discord_invite_url": settings.DISCORD_INVITE_URL or "https://discord.gg/G568r5MFqB"
    }

@router.get("/tournaments", response_model=List[Dict[str, Any]], summary="Get Detailed Tournament List")
async def get_public_tournaments():
    """Return list of active tournaments with details for public display."""
    try:
        tournaments = await get_tournaments_detailed()
        return tournaments
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching tournaments: {str(e)}"
        )

@router.get("/tournaments/{slug}", response_model=Dict[str, Any], summary="Get Tournament by Slug")
async def get_public_tournament(slug: str):
    """Return single tournament details by slug or title."""
    tournament = await get_tournament_by_slug(slug)
    if not tournament:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tournament with identifier '{slug}' was not found."
        )
    return tournament

@router.get("/tournaments/{slug}/approved-teams", response_model=List[Dict[str, Any]], summary="Get Approved Teams")
async def get_public_approved_teams(slug: str):
    """
    Return all APPROVED registrations for the specified tournament.
    Sanitized for public website display: NO phone numbers, NO internal DB IDs, NO admin info.
    """
    approved_teams = await get_approved_teams_by_tournament(slug)
    return approved_teams

@router.get("/stats", response_model=Dict[str, Any], summary="Get Public Platform Stats")
async def get_public_stats():
    """Return public platform statistics."""
    stats = await get_platform_stats()
    return stats

@router.get("/matches", response_model=List[Dict[str, Any]], summary="Get Public Matches")
async def get_public_match_list():
    """Return public match records (live, upcoming, completed)."""
    matches = await get_public_matches()
    return matches
