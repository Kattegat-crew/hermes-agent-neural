import pytest
from tools.environments.local_env_policy import _is_provider_env_blocklisted
from agent.redact import redact_sensitive_text

SENSITIVE_FLEET_KEYS = [
    "PG_RO_DSN", "SUDO_PASSWORD", "NAN_API_KEY", "NAN_BUILDERS_API_KEY",
    "OPENCODE_GO_API_KEY", "COMPOSIO_KEY", "TYPESAFE_API_KEY", "CONTEXT7_API_KEY",
    "PAPERLESS_API_KEY", "CLOUDFLARE_MCP_TOKEN", "CLOUDFLARE_MCP_TOKEN_WRITER",
    "COOLIFY_MCP_TOKEN", "GITHUB_MCP_TOKEN", "PAPERLESS_MCP_TOKEN",
    "DOCUSEAL_MCP_TOKEN", "STIRLING_MCP_KEY", "FORMBRICKS_MCP_KEY_RO",
    "FORMBRICKS_MCP_KEY_RW", "OUTLINE_MCP_TOKEN", "TWENTY_MCP_KEY_GOLDEN",
    "TWENTY_MCP_KEY_LUCKY", "TWENTY_MCP_KEY_NC", "TWENTY_MCP_KEY_GOLDEN_WRITER",
    "TWENTY_MCP_KEY_LUCKY_WRITER", "TWENTY_MCP_KEY_NC_WRITER",
    "AMAZON_SPAPI_CLIENT_ID", "AMAZON_SPAPI_CLIENT_SECRET",
    "AMAZON_SPAPI_REFRESH_TOKEN", "AMAZON_SPAPI_NA_REFRESH_TOKEN",
    "AMAZON_SPAPI_SANDBOX_CLIENT_ID", "AMAZON_SPAPI_SANDBOX_CLIENT_SECRET",
    "AMAZON_SPAPI_SANDBOX_REFRESH_TOKEN", "HERMES_LANGFUSE_SECRET_KEY",
    "A2A_BEARER_TOKEN", "WEBHOOK_SECRET", "BW_PASSWORD", "BW_CLIENTSECRET",
    "BW_SESSION", "BWS_ACCESS_TOKEN"
]

@pytest.mark.parametrize("key", SENSITIVE_FLEET_KEYS)
def test_fleet_secrets_are_blocklisted(key):
    assert _is_provider_env_blocklisted(key)
    assert _is_provider_env_blocklisted(key.lower())

def test_dynamic_pattern_blocklisting():
    assert _is_provider_env_blocklisted("RANDOM_CUSTOM_MCP_TOKEN")
    assert _is_provider_env_blocklisted("CUSTOM_SERVICE_MCP_KEY")
    assert _is_provider_env_blocklisted("AMAZON_SPAPI_ARBITRARY_FIELD")

def test_sensitive_assignments_redaction():
    text = (
        "PG_RO_DSN=postgresql://hermes:supersecret@127.0.0.1:5432/ncl\n"
        "OUTLINE_MCP_TOKEN=ol_secret_token_12345\n"
        "AMAZON_SPAPI_CLIENT_ID=amzn_client_999\n"
        "TWENTY_MCP_KEY_NC=twenty_nc_secret_key"
    )
    redacted = redact_sensitive_text(text)
    assert "supersecret" not in redacted
    assert "ol_secret_token_12345" not in redacted
    assert "amzn_client_999" not in redacted
    assert "twenty_nc_secret_key" not in redacted


def test_dynamic_secret_source_sanitization():
    from hermes_cli.env_loader import _SECRET_SOURCES
    _SECRET_SOURCES["SYNTHETIC_DYNAMIC_KEY"] = "command"
    try:
        assert _is_provider_env_blocklisted("SYNTHETIC_DYNAMIC_KEY")
        assert _is_provider_env_blocklisted("synthetic_dynamic_key")
    finally:
        _SECRET_SOURCES.pop("SYNTHETIC_DYNAMIC_KEY", None)


def test_subprocess_env_stripping():
    from tools.environments.local import _sanitize_subprocess_env
    from hermes_cli.env_loader import _SECRET_SOURCES
    _SECRET_SOURCES["TEST_SECRET_FROM_SOURCE"] = "command"
    try:
        env = {
            "PATH": "/bin",
            "SAFE_CONFIG": "visible",
            "TEST_SECRET_FROM_SOURCE": "secret_value_123",
            "CLOUDFLARE_MCP_TOKEN": "token_val_456",
        }
        sanitized = _sanitize_subprocess_env(env)
        assert "SAFE_CONFIG" in sanitized
        assert "TEST_SECRET_FROM_SOURCE" not in sanitized
        assert "CLOUDFLARE_MCP_TOKEN" not in sanitized
    finally:
        _SECRET_SOURCES.pop("TEST_SECRET_FROM_SOURCE", None)

