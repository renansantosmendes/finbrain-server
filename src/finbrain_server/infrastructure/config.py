"""Settings read from environment variables (prefix ``FINBRAIN_``)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from finbrain_server.application.cache_policy import CachePolicy

DEFAULT_WATCHLIST = "PETR4.SA,VALE3.SA,ITUB4.SA,^BVSP,AAPL,BRL=X"


class Settings(BaseSettings):
    """Configuration of the FinBrain server.

    Every field can be set with an environment variable, for example
    ``FINBRAIN_CORS_ORIGINS=https://finbrain.vercel.app``.
    """

    model_config = SettingsConfigDict(
        env_prefix="FINBRAIN_",
        env_file=".env",
        extra="ignore",
    )

    cors_origins_raw: str = Field(
        default="*",
        alias="FINBRAIN_CORS_ORIGINS",
        description="Comma-separated origins allowed by CORS; '*' allows all.",
    )
    watchlist: str = Field(
        default=DEFAULT_WATCHLIST,
        description="Tickers of the dashboard when the client sends none.",
    )
    cache_max_entries: int = Field(default=512, ge=16, le=100000)
    cache_ttl_quote: float = Field(default=60, ge=0)
    cache_ttl_history: float = Field(default=900, ge=0)
    cache_ttl_intraday_history: float = Field(default=60, ge=0)
    cache_ttl_fundamentals: float = Field(default=21600, ge=0)
    cache_ttl_macro: float = Field(default=21600, ge=0)
    cache_ttl_world_bank: float = Field(default=86400, ge=0)
    cache_ttl_crypto_ticker: float = Field(default=15, ge=0)
    cache_ttl_crypto_ohlcv: float = Field(default=60, ge=0)
    cache_ttl_order_book: float = Field(default=5, ge=0)
    cache_ttl_exchanges: float = Field(default=86400, ge=0)
    cache_ttl_simulation: float = Field(default=3600, ge=0)

    @property
    def cors_origins(self) -> list[str]:
        """Origins allowed by CORS.

        Returns
        -------
        list[str]
            Origins, or ``["*"]`` to allow every origin.
        """
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]

    @property
    def cache_policy(self) -> CachePolicy:
        """Time to live of each kind of cached data.

        Returns
        -------
        CachePolicy
            Policy built from the ``cache_ttl_*`` fields.
        """
        return CachePolicy(
            quote=self.cache_ttl_quote,
            history=self.cache_ttl_history,
            intraday_history=self.cache_ttl_intraday_history,
            fundamentals=self.cache_ttl_fundamentals,
            macro=self.cache_ttl_macro,
            world_bank=self.cache_ttl_world_bank,
            crypto_ticker=self.cache_ttl_crypto_ticker,
            crypto_ohlcv=self.cache_ttl_crypto_ohlcv,
            order_book=self.cache_ttl_order_book,
            exchanges=self.cache_ttl_exchanges,
            simulation=self.cache_ttl_simulation,
        )


@lru_cache
def get_settings() -> Settings:
    """Settings of the process, read once.

    Returns
    -------
    Settings
        Shared settings instance.
    """
    return Settings()
