"""Validated contracts shared by analysis, risk and execution."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RiskStyle(str, Enum):
    conservative = "conservative"
    balanced = "balanced"
    high_risk = "high-risk"
    capital_preservation = "capital_preservation"
    growth = "growth"


class ExecutionMode(str, Enum):
    observe = "observe"
    recommend_approve = "recommend_approve"
    bounded_autopilot = "bounded_autopilot"


class Side(str, Enum):
    buy = "buy"
    sell = "sell"


class UserMandate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocated_capital: float = Field(gt=0)
    risk_style: RiskStyle
    max_loss_per_trade: float = Field(gt=0)
    max_daily_loss: float = Field(gt=0)
    max_position_size: float = Field(gt=0)
    auto_execution_mode: ExecutionMode


class TradeProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=12, pattern=r"^[A-Z][A-Z0-9.\-]*$")
    side: Side
    qty: float = Field(gt=0)
    target_entry_price: float = Field(gt=0)
    stop_loss_price: float = Field(gt=0)
    take_profit_price: float = Field(gt=0)
    bull_argument: str = Field(min_length=1)
    bear_argument: str = Field(min_length=1)
    judge_summary: str = Field(min_length=1)
    confidence_score: float = Field(ge=0, le=1)
    estimated_upside_pct: float
    estimated_downside_pct: float

    @field_validator("symbol", mode="before")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper() if isinstance(value, str) else value


class FirewallVerdict(BaseModel):
    passed: bool
    rejected_reasons: list[str]
    proposal: TradeProposal
