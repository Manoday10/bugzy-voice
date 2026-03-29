import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

class HTTPClient:
    """
    Singleton wrapper for httpx.AsyncClient to be used across the application.
    Ensures efficient connection pooling and reuse.
    """
    _client: Optional[httpx.AsyncClient] = None

    @classmethod
    def get_client(cls) -> httpx.AsyncClient:
        """
        Get the shared AsyncClient instance.
        If it hasn't been initialized (e.g. outside lifespan), 
        logs a warning and creates a temporary one (not ideal but safe).
        """
        if cls._client is None:
            logger.warning("⚠️ HTTPClient accessed before initialization! Creating a new instance implicitly.")
            cls._client = httpx.AsyncClient(timeout=30.0)
        return cls._client

    @classmethod
    async def start(cls):
        """Initialize the AsyncClient. Call this on app startup."""
        if cls._client is None or cls._client.is_closed:
            logger.info("🚀 Initializing shared HTTPClient.")
            # Standard timeout of 30s, can be adjusted.
            # Limits can be tuned: default is 100 max connections, 10 keepalive.
            cls._client = httpx.AsyncClient(timeout=30.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))

    @classmethod
    async def close(cls):
        """Close the AsyncClient. Call this on app shutdown."""
        if cls._client:
            logger.info("🛑 Closing shared HTTPClient.")
            await cls._client.aclose()
            cls._client = None
