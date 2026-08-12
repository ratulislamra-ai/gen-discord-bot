from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader, APIKeyQuery
import config.settings as settings

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
