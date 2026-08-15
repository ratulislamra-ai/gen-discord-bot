import json
import urllib.parse
import urllib.request
import asyncio
from fastapi import APIRouter, Response, Request, Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
from fastapi.responses import RedirectResponse, JSONResponse
import config.settings as settings
from database.db import get_or_create_player, get_player_full_profile, get_user_all_registrations, get_user_notifications

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

async def verify_api_key(
    header_key: str = Security(api_key_header),
    query_key: str = Security(api_key_query)
) -> str:
    """
    FastAPI dependency to authenticate requests using X-API-Key header or api_key query parameter.
    Returns 401 Unauthorized for invalid keys.
    """
    api_key = header_key or query_key
    
    if not settings.GEN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server error: GEN_API_KEY is not configured on the server."
        )
        
    if not api_key or api_key != settings.GEN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key."
        )
        
    return api_key

auth_router = APIRouter(prefix="/api/auth", tags=["Discord OAuth2 Authentication"])

def _exchange_discord_code_sync(code: str):
    url = "https://discord.com/api/oauth2/token"
    data = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "client_secret": settings.DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.DISCORD_REDIRECT_URI
    }
    encoded_data = urllib.parse.urlencode(data).encode("utf-8")
    req = urllib.request.Request(url, data=encoded_data, headers={
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "GENEsportsBot/1.0"
    })
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

def _fetch_discord_user_sync(access_token: str):
    url = "https://discord.com/api/users/@me"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {access_token}",
        "User-Agent": "GENEsportsBot/1.0"
    })
    with urllib.request.urlopen(req, timeout=10.0) as resp:
        return json.loads(resp.read().decode("utf-8"))

@auth_router.get("/discord/login")
async def discord_oauth_login():
    """Redirect to Discord OAuth2 Authorization page."""
    if not settings.DISCORD_CLIENT_ID:
        return JSONResponse({
            "error": "DISCORD_CLIENT_ID not configured",
            "auth_url": None,
            "message": "Discord OAuth2 client credentials are not configured in .env."
        }, status_code=status.HTTP_400_BAD_REQUEST)

    params = {
        "client_id": settings.DISCORD_CLIENT_ID,
        "redirect_uri": settings.DISCORD_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify email"
    }
    auth_url = f"https://discord.com/api/oauth2/authorize?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=auth_url)

@auth_router.get("/discord/callback")
async def discord_oauth_callback(code: str | None = None, error: str | None = None):
    """Handle OAuth2 callback from Discord."""
    if error or not code:
        return RedirectResponse(url="/#dashboard?auth_error=cancelled")

    try:
        token_data = await asyncio.to_thread(_exchange_discord_code_sync, code)
        access_token = token_data.get("access_token")
        if not access_token:
            return RedirectResponse(url="/#dashboard?auth_error=token_failed")

        user_info = await asyncio.to_thread(_fetch_discord_user_sync, access_token)
        discord_id = str(user_info["id"])
        username = user_info.get("username", "Player")
        display_name = user_info.get("global_name") or username
        avatar_hash = user_info.get("avatar")
        avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar_hash}.png" if avatar_hash else ""

        await get_or_create_player(discord_id, username, display_name, avatar_url)

        response = RedirectResponse(url="/#dashboard?login=success")
        response.set_cookie(key="gen_user_id", value=discord_id, httponly=False, max_age=86400 * 30)
        return response
    except Exception as e:
        return RedirectResponse(url=f"/#dashboard?auth_error={urllib.parse.quote(str(e))}")

@auth_router.get("/me")
async def get_current_user_profile(user_id: str | None = None, request: Request = None):
    """Get authenticated user identity and full dashboard state."""
    active_user_id = user_id or (request.cookies.get("gen_user_id") if request else None)
    if not active_user_id:
        return JSONResponse({"authenticated": False, "player": None})

    profile = await get_player_full_profile(str(active_user_id))
    registrations = await get_user_all_registrations(str(active_user_id))
    notifications = await get_user_notifications(str(active_user_id))

    return {
        "authenticated": True,
        "user_id": str(active_user_id),
        "profile": profile,
        "registrations": registrations,
        "notifications": notifications
    }

@auth_router.post("/logout")
async def logout(response: Response):
    """Logout current user by clearing session cookie."""
    response.delete_cookie(key="gen_user_id")
    return {"message": "Logged out successfully."}

