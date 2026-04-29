# backend/app/api/middleware/auth_middleware.py
from starlette.middleware.base import (
    BaseHTTPMiddleware, RequestResponseEndpoint
)
from starlette.requests import Request
from starlette.responses import JSONResponse
from jose import jwt, JWTError
from app.config import get_settings
import httpx
import logging
import os

logger = logging.getLogger(__name__)

# Paths that don't require authentication
PUBLIC_PATHS = {"/health", "/api/docs", "/openapi.json", "/docs", "/redoc"}
# Developer bypass configuration (for local testing)
DEVELOPER_BYPASS_HEADER = "X-Developer-Id"



class AzureADAuthMiddleware(BaseHTTPMiddleware):
    """
    Validates Azure AD Bearer tokens on all protected endpoints.
    Uses JWKS endpoint for key verification.
    """

    def __init__(self, app):
        super().__init__(app)
        self.settings = get_settings()
        self.tenant_id = self.settings.azure_tenant_id
        self.client_id = self.settings.azure_client_id
        self.jwks_uri = (
            f"https://login.microsoftonline.com/"
            f"{self.tenant_id}/discovery/v2.0/keys"
        )
        self.issuer = (
            f"https://login.microsoftonline.com/"
            f"{self.tenant_id}/v2.0"
        )
        self._jwks_cache = None

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ):
        # Skip auth for public paths
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Check for Developer Bypass (only if enabled via env)
        allow_bypass = os.getenv("ALLOW_AUTH_BYPASS", "false").lower() == "true"
        dev_id = request.headers.get(DEVELOPER_BYPASS_HEADER) or "local_dev_user"
        if allow_bypass:
            logger.info(f"Using developer bypass for user: {dev_id}")
            request.state.user_id = dev_id
            request.state.user_email = f"{dev_id}@dev.local"
            request.state.user_name = f"Dev User ({dev_id})"
            request.state.user_roles = ["admin", "developer"]
            return await call_next(request)

        # Extract Bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing or invalid authorization header"},
            )


        token = auth_header.split("Bearer ")[1]

        try:
            # Validate token
            claims = await self._validate_token(token)
            
            # Attach claims to request state
            request.state.token_claims = claims
            request.state.user_id = claims.get("oid", "")
            request.state.user_email = claims.get(
                "preferred_username", ""
            )
            request.state.user_name = claims.get("name", "")
            request.state.user_roles = claims.get("roles", [])

        except JWTError as e:
            logger.warning(f"Token validation failed: {e}")
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )
        except Exception as e:
            logger.error(f"Auth middleware error: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Authentication service error"},
            )

        return await call_next(request)

    async def _validate_token(self, token: str) -> dict:
        """Validate JWT token against Azure AD JWKS."""
        if not self._jwks_cache:
            async with httpx.AsyncClient() as client:
                resp = await client.get(self.jwks_uri)
                self._jwks_cache = resp.json()

        # Decode without verification first to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")

        # Find matching key
        rsa_key = None
        for key in self._jwks_cache.get("keys", []):
            if key["kid"] == kid:
                rsa_key = key
                break

        if not rsa_key:
            raise JWTError("Unable to find matching key")

        # Validate and decode
        claims = jwt.decode(
            token,
            rsa_key,
            algorithms=["RS256"],
            audience=self.client_id,
            issuer=self.issuer,
        )

        return claims
