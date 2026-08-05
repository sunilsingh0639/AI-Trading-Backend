from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    company_name: str = Field(min_length=2, max_length=200)
    symbol: str = Field(min_length=1, max_length=50)
    exchange: str = Field(default="NSE", min_length=2, max_length=20)
    sector: str | None = Field(default=None, max_length=100)
    industry: str | None = Field(default=None, max_length=100)
    is_fno: bool = False
    is_active: bool = True

    @field_validator("symbol", "exchange")
    @classmethod
    def uppercase_market_identifiers(cls, value: str) -> str:
        return value.upper()


class NewsAnalysisResult(BaseModel):
    """The constrained contract accepted from the LLM provider."""

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    stock_name: str = Field(default="MARKET", min_length=2, max_length=100)
    symbol: str | None = Field(default=None, max_length=50)
    sector: str = Field(default="MARKET", min_length=2, max_length=100)
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"]
    confidence: int = Field(ge=0, le=100)
    impact: Literal["LOW", "MEDIUM", "HIGH"]
    recommendation: Literal["BUY", "SELL", "HOLD"]
    reason: str = Field(min_length=8, max_length=1500)

    @field_validator("sentiment", "impact", "recommendation", mode="before")
    @classmethod
    def normalise_enums(cls, value: str) -> str:
        return str(value).strip().upper()

    @field_validator("stock_name", "sector", mode="before")
    @classmethod
    def normalise_labels(cls, value: str | None) -> str:
        cleaned = str(value or "").strip()
        return cleaned or "MARKET"

    @field_validator("symbol", mode="before")
    @classmethod
    def normalise_symbol(cls, value: str | None) -> str | None:
        if not value:
            return None
        return str(value).strip().upper()
