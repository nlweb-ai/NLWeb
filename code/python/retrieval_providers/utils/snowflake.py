"""Functions for extracting Snowflake connection parameters from configuration."""

from core.config import CONFIG, LLMProviderConfig, EmbeddingProviderConfig, RetrievalProviderConfig

class ConfigurationError(RuntimeError):
    """Raised when configuration is missing or invalid"""
    pass

def get_pat(cfg: LLMProviderConfig|EmbeddingProviderConfig|RetrievalProviderConfig) -> str:
    """
    Retrieve the Programmatic Access Token (PAT) from the environment, or raise an error.
    """
    pat = cfg.api_key.strip('"') if cfg and cfg.api_key else None
    if not pat:
        raise ConfigurationError(f"Unable to determine Snowflake Programmatic Access Token to use (PAT), is SNOWFLAKE_PAT set?")
    return pat


def get_account_url(cfg: LLMProviderConfig|EmbeddingProviderConfig|RetrievalProviderConfig) -> str:
    """
    Retrieve the account URL that is the base URL for all Snowflake Cortex API REST calls, or raise an error.
    """
    # Unfortunately, LLMProviderCondfig and EmbeddingProviderConfig use 'endpoint'
    # while RetrievalProviderConfig uses 'api_endpoint', so handle both.
    endpoint = cfg.api_endpoint if isinstance(cfg, RetrievalProviderConfig) else cfg.endpoint
    account_url = endpoint.strip('"')
    if not account_url:
        raise ConfigurationError(f"Unable to determine Snowflake Account URL, is SNOWFLAKE_ACCOUNT_URL set?")
    return account_url
