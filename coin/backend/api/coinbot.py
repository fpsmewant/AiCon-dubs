"""Demo-only CoinBot controls and state."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine import coinbot


router = APIRouter(prefix="/api/coinbot", tags=["coinbot"])


class CoinBotConfig(BaseModel):
    max_window_spend: float = Field(20, gt=0, le=10000)
    take_profit_pct: float = Field(15, gt=0, le=100)
    stop_loss_pct: float = Field(12, gt=0, le=100)


@router.get("/status")
def status():
    return coinbot.status()


@router.post("/start")
def start(config: CoinBotConfig):
    try:
        return coinbot.start(config)
    except Exception as exc:
        raise HTTPException(503, f"Demo account could not be connected: {exc}") from exc


@router.post("/stop")
def stop():
    return coinbot.stop()


@router.post("/close")
def close():
    try:
        return coinbot.close_position()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Could not close the demo position.") from exc
