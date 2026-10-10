"""US stock paper CoinBot controls and state."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from engine import coinbot


router = APIRouter(prefix="/api/coinbot", tags=["coinbot"])


class CoinBotConfig(BaseModel):
    max_trade_budget: float = Field(1000, gt=0, le=100000)
    take_profit_pct: float = Field(3, gt=0, le=25)
    stop_loss_pct: float = Field(1.5, gt=0, le=20)


@router.get("/status")
def status():
    return coinbot.status()


@router.post("/start")
def start(config: CoinBotConfig):
    try:
        return coinbot.start(config)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(503, "Paper account could not be connected.") from exc


@router.post("/stop")
def stop():
    return coinbot.stop()


@router.post("/select/{symbol}")
def select(symbol: str):
    try:
        return coinbot.select_symbol(symbol.upper())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/close")
def close():
    try:
        return coinbot.close_position()
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, "Could not close the paper position.") from exc
