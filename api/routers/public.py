from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
import config.settings as settings
from database.db import (
    get_tournaments_detailed,
    get_tournament_by_slug,
    get_approved_teams_by_tournament,
    get_platform_stats,
    get_public_matches,
    get_tournament_matches,
    get_tournament_standings,
    get_user_all_registrations,
    get_user_all_cases,
    get_support_ticket_by_case_id,
    get_all_players_public,
    get_player_full_profile,
    get_all_teams_public,
    get_team_full_profile
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

@router.get("/tournaments/{slug}/matches", response_model=List[Dict[str, Any]], summary="Get Matches for Tournament")
async def get_public_tournament_matches(slug: str):
    """Return matches for a specific tournament."""
    matches = await get_tournament_matches(slug)
    return matches

@router.get("/tournaments/{slug}/bracket", response_model=List[Dict[str, Any]], summary="Get Bracket for Tournament")
async def get_public_tournament_bracket(slug: str):
    """Return bracket matches for a specific tournament."""
    matches = await get_tournament_matches(slug)
    return matches

@router.get("/tournaments/{slug}/standings", response_model=List[Dict[str, Any]], summary="Get Standings for Tournament")
async def get_public_tournament_standings(slug: str):
    """Return leaderboard standings for a specific tournament."""
    standings = await get_tournament_standings(slug)
    return standings

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

@router.get("/players", response_model=List[Dict[str, Any]], summary="Get Public Players Directory")
async def get_players_directory_api():
    """Return public players directory list (sanitized)."""
    players = await get_all_players_public()
    return players

@router.get("/players/{slug}", response_model=Dict[str, Any], summary="Get Public Player Profile")
async def get_player_profile_api(slug: str):
    """Return single public player profile (sanitized: NO Discord ID, NO phone, NO private support data)."""
    profile = await get_player_full_profile(slug)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Player '{slug}' not found.")
    return profile

@router.get("/teams", response_model=List[Dict[str, Any]], summary="Get Public Teams Directory")
async def get_teams_directory_api():
    """Return public teams directory list (sanitized)."""
    teams = await get_all_teams_public()
    return teams

@router.get("/teams/{slug}", response_model=Dict[str, Any], summary="Get Public Team Profile")
async def get_team_profile_api(slug: str):
    """Return single public team profile with active roster & tournament history."""
    profile = await get_team_full_profile(slug)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Team '{slug}' not found.")
    return profile

@router.get("/user/registrations", response_model=List[Dict[str, Any]], summary="Get User Registrations")
async def get_user_registrations_api(user_id: str):
    """Return team registrations created by a Discord user ID (sanitized)."""
    regs = await get_user_all_registrations(user_id)
    return regs

@router.get("/user/cases", response_model=List[Dict[str, Any]], summary="Get User Support Cases")
async def get_user_cases_api(user_id: str):
    """Return support cases created by a Discord user ID."""
    cases = await get_user_all_cases(user_id)
    return cases

@router.get("/user/dashboard", response_model=Dict[str, Any], summary="Get Full User Dashboard Overview")
async def get_user_dashboard_api(user_id: str):
    """Return user profile, active teams, registrations, and support cases for dashboard rendering."""
    profile = await get_player_full_profile(user_id)
    regs = await get_user_all_registrations(user_id)
    cases = await get_user_all_cases(user_id)
    
    return {
        "profile": profile,
        "registrations": regs,
        "cases": cases
    }

