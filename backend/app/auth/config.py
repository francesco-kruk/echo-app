"""Authentication configuration for Entra ID."""

import os
from functools import lru_cache
from pydantic import BaseModel


class AuthSettings(BaseModel):
    """Authentication settings loaded from environment variables."""

    tenant_id: str = ""
    api_audience: str = ""  # The Application ID URI (e.g., api://<app-id>)
    api_app_id: str = ""  # The Backend API App ID
    enabled: bool = True  # Set to False to disable auth (for local dev without Entra)

    @property
    def authority(self) -> str:
        """Get the Entra ID authority URL."""
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def issuer(self) -> str:
        """Get the expected token issuer (v2.0 format)."""
        return f"https://login.microsoftonline.com/{self.tenant_id}/v2.0"

    @property
    def issuer_v1(self) -> str:
        """Get the expected token issuer (v1.0 format)."""
        return f"https://sts.windows.net/{self.tenant_id}/"

    @property
    def valid_issuers(self) -> list[str]:
        """Get all valid token issuers (both v1.0 and v2.0 formats)."""
        return [self.issuer, self.issuer_v1]

    @property
    def openid_config_url(self) -> str:
        """Get the OpenID Connect configuration URL."""
        return f"{self.authority}/v2.0/.well-known/openid-configuration"

    @property
    def jwks_uri(self) -> str:
        """Get the JWKS URI for token validation."""
        return f"https://login.microsoftonline.com/{self.tenant_id}/discovery/v2.0/keys"

    def is_configured(self) -> bool:
        """Check if auth is properly configured."""
        return bool(self.tenant_id and self.api_audience)


@lru_cache()
def get_auth_settings() -> AuthSettings:
    """Get cached authentication settings from environment variables."""
    enabled_str = os.getenv("AUTH_ENABLED", "true").lower()
    enabled = enabled_str not in ("false", "0", "no", "off")

    return AuthSettings(
        tenant_id=os.getenv("AZURE_TENANT_ID", os.getenv("TENANT_ID", "")),
        api_audience=os.getenv("AZURE_API_SCOPE", os.getenv("API_AUDIENCE", "")),
        api_app_id=os.getenv("AZURE_API_APP_ID", os.getenv("API_APP_ID", "")),
        enabled=enabled,
    )
