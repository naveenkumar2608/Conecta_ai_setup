# backend/app/api/v1/auth.py
from fastapi import APIRouter, Depends, HTTPException, Request
from app.models.api_models import (
    TokenValidationResponse, UserProfileResponse
)
from app.dependencies import get_current_user
from app.models.api_models import UserContext

router = APIRouter()


@router.post("/validate", response_model=TokenValidationResponse)
async def validate_token(request: Request):
    """
    Validate Azure AD Bearer token.
    Used by frontend to verify token validity before making API calls.
    
    The actual token validation happens in AzureADAuthMiddleware.
    This endpoint confirms the token is valid and returns claims.
    """
    # Token is validated by middleware; extract claims
    token_claims = getattr(request.state, "token_claims", None)
    if not token_claims:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    return TokenValidationResponse(
        valid=True,
        user_id=token_claims.get("oid", ""),
        email=token_claims.get("preferred_username", ""),
        name=token_claims.get("name", ""),
        roles=token_claims.get("roles", []),
        expires_at=token_claims.get("exp", 0),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    user: UserContext = Depends(get_current_user),
):
    """
    Get current authenticated user's profile.
    Data comes from Azure AD token claims.
    """
    return UserProfileResponse(
        user_id=user.user_id,
        email=user.email,
        display_name=user.display_name,
        roles=user.roles,
        region=user.region,
    )