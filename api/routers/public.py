from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from typing import List, Dict, Any
import config.settings as settings
from database.db import (
    get_tournaments_detailed,
    get_tournament_by_slug,
    get_approved_teams_by_tournament,
    get_platform_stats,
    get_public_matches,
    get_tournament_matches,
    get_tournament_bracket_tree,
    get_tournament_standings,
    get_user_all_registrations,
    get_user_all_cases,
    get_support_ticket_by_case_id,
    get_all_players_public,
    get_player_full_profile,
    get_all_teams_public,
    get_team_full_profile,
    process_match_check_in,
    submit_match_score,
    confirm_opponent_match_score
)

router = APIRouter(prefix="/api/public", tags=["Public Website Endpoints"])

@router.post("/matches/{match_id}/check-in", summary="Team Match Check-In")
async def match_check_in_api(match_id: int, payload: Dict[str, Any]):
    """Process team check-in for a match."""
    team_id = payload.get("team_id")
    if not team_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id is required.")
    
    match = await process_match_check_in(match_id, int(team_id))
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found or invalid team.")
    return {"message": "Check-in recorded successfully.", "match": match}

@router.post("/matches/{match_id}/submit-result", summary="Submit Match Score & Evidence")
async def submit_match_score_api(match_id: int, payload: Dict[str, Any]):
    """Submit match result. Transitions status to OPPONENT_CONFIRMATION."""
    team_id = payload.get("submitting_team_id", 0)
    user_id = payload.get("submitting_user_id", "")
    score_a = payload.get("score_a", 0)
    score_b = payload.get("score_b", 0)
    evidence_url = payload.get("evidence_url", "")

    match = await submit_match_score(match_id, int(team_id), str(user_id), int(score_a), int(score_b), evidence_url)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    return {"message": "Score submitted! Awaiting opponent confirmation.", "match": match}

@router.post("/matches/{match_id}/confirm-result", summary="Opponent Confirm or Dispute Match Score")
async def confirm_match_score_api(match_id: int, payload: Dict[str, Any]):
    """Confirm or dispute opponent match score submission."""
    user_id = payload.get("confirming_user_id", "")
    accept = payload.get("accept", True)
    dispute_reason = payload.get("dispute_reason", "")

    match = await confirm_opponent_match_score(match_id, str(user_id), bool(accept), dispute_reason)
    if not match:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Match not found.")
    return {"message": "Opponent response recorded successfully.", "match": match}

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
    approved_teams = await get_approved_teams_by_tournament(slug)
    return {
        "tournament": tournament,
        "approved_teams": approved_teams
    }

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

@router.get("/tournaments/{slug}/bracket", response_model=Dict[str, Any], summary="Get Bracket Tree for Tournament")
async def get_public_tournament_bracket(slug: str):
    """Return structured bracket tree (rounds, matches, champion, has_bracket) for a specific tournament."""
    tree = await get_tournament_bracket_tree(slug)
    return tree

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

@router.get("/health", summary="Get Public System Health Status")
async def get_public_health_status_api():
    """Return basic health indicator."""
    return {"status": "HEALTHY", "service": "GEN Esports Platform API"}

@router.get("/search", summary="Global Platform Search")
async def global_search_api(q: str):
    """Global search across players, teams, tournaments, and matches."""
    from database.db import global_platform_search
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Search query must be at least 2 characters.")
    res = await global_platform_search(q)
    return res

@router.get("/user/notifications", summary="Get User Notifications")
async def get_user_notifications_api(user_id: str):
    """Return recent notifications for a user."""
    from database.db import get_user_notifications
    notifs = await get_user_notifications(user_id)
    return notifs

@router.get("/tournaments/{tournament_id}/economy", summary="Get Tournament Economy & Prize Pool")
async def get_tournament_economy_api(tournament_id: int):
    """Return prize pool distribution and ledger overview."""
    from database.db import get_tournament_financial_overview
    overview = await get_tournament_financial_overview(tournament_id)
    return overview

@router.get("/leaderboard", summary="Get Competitive Leaderboard")
async def get_leaderboard_api(game: str = "VALORANT"):
    """Return competitive team & player leaderboards filtered by game."""
    from database.db import get_public_leaderboard
    res = await get_public_leaderboard(game)
    return res

@router.get("/seasons", summary="Get Competitive Seasons List")
async def get_seasons_api():
    """Return active & historical competitive seasons."""
    from database.db import get_seasons_list
    seasons = await get_seasons_list()
    return seasons

@router.get("/live", summary="Get Live Spectator Matches & Broadcast Streams")
async def get_live_spectator_hub_api():
    """Return live spectator matches with stream URLs and score telemetry."""
    from database.db import get_live_spectator_matches
    matches = await get_live_spectator_matches()
    return matches

@router.get("/tournaments/{tournament_id}/rules", summary="Get Tournament Ruleset")
async def get_tournament_ruleset_api(tournament_id: int):
    """Return tournament ruleset, BO3 veto sequence, allowed maps, and version."""
    from database.db import get_or_create_tournament_ruleset
    rules = await get_or_create_tournament_ruleset(tournament_id)
    return rules

@router.get("/matches/{match_id}/veto", summary="Get Match Veto Session State")
async def get_match_veto_api(match_id: int):
    """Return live map veto session state and ban/pick log history."""
    from database.db import get_match_veto_state
    state = await get_match_veto_state(match_id)
    if not state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Veto session not found for match.")
    return state

@router.post("/matches/{match_id}/veto/action", summary="Execute Map Veto Ban/Pick Turn")
async def process_veto_action_api(match_id: int, payload: Dict[str, Any]):
    """Execute a map ban or pick turn in a veto session."""
    from database.db import process_veto_action
    acting_team_id = payload.get("team_id")
    map_name = payload.get("map_name")

    if not acting_team_id or not map_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="team_id and map_name are required.")

    state = await process_veto_action(match_id, int(acting_team_id), str(map_name))
    if not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid map action or unauthorized turn.")
    return {"message": "Veto action recorded.", "veto": state}

@router.post("/matches/upload-evidence", summary="Upload Match Result Evidence Screenshot")
async def upload_match_evidence_api(
    file: UploadFile = File(...),
    match_id: int | None = Form(None)
):
    """Securely upload a match result screenshot (PNG, JPG, WEBP <= 10MB)."""
    from utils.match_evidence_storage import save_match_evidence

    if not file or not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file uploaded.")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size exceeds the 10 MB maximum limit.")

    try:
        local_path, relative_url = save_match_evidence(content, file.filename, match_id)
        return {
            "success": True,
            "url": relative_url,
            "filename": file.filename,
            "size": len(content)
        }
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload screenshot: {str(e)}")


