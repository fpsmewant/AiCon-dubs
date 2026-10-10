import re

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from db.mandates import load_mandate, save_mandate
from engine import orchestrator
from execution.alpaca_client import AlpacaClient
from execution.broker_adapter import IBroker
from intelligence.generators import TradeProposal, UserMandate
from intelligence.data_feeds.market_data import market_summary, daily_history
from intelligence.helpers.opportunity import rank_opportunities
from intelligence.voice.guide import GuidePlan, INVESTING_TERMS, build_guide, invalid_plan
from intelligence.voice.transcription import transcribe_audio
from intelligence.voice.response import VisualAnswer, answer, mentioned_symbol
from intelligence.data_feeds.marketaux import cached_news, sync_news


router = APIRouter(prefix="/api")


@router.get('/market')
def market() -> dict:
    try:
        return market_summary()
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Market feed unavailable. Please retry shortly.') from exc


def get_broker() -> IBroker:
    try:
        return AlpacaClient()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def required_mandate() -> UserMandate:
    mandate = load_mandate()
    if mandate is None:
        raise HTTPException(status_code=409, detail="Save a user mandate before reviewing or executing trades")
    return mandate


@router.get("/account")
def account(broker: IBroker = Depends(get_broker)) -> dict:
    try:
        return orchestrator.account_snapshot(broker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Alpaca account sync failed. Check paper credentials and network access.") from exc


@router.get("/mandate", response_model=UserMandate)
def get_mandate(mandate: UserMandate = Depends(required_mandate)) -> UserMandate:
    return mandate


@router.post("/mandate", response_model=UserMandate)
def set_mandate(mandate: UserMandate) -> UserMandate:
    return save_mandate(mandate)


@router.post("/analyze/{symbol}", response_model=TradeProposal)
def analyze(symbol: str) -> TradeProposal:
    symbol = symbol.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9.\-]{0,11}", symbol):
        raise HTTPException(status_code=422, detail="Invalid stock symbol")
    try:
        return orchestrator.analyze(symbol)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Live market data is unavailable. Check paper credentials and network access.") from exc


def checked_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}', symbol):
        raise HTTPException(status_code=422, detail='Invalid stock symbol')
    return symbol


@router.post('/debate/{side}/{symbol}')
def debate(side: str, symbol: str) -> dict:
    symbol = checked_symbol(symbol)
    if side not in ('bull', 'bear'):
        raise HTTPException(status_code=422, detail='Side must be bull or bear')
    try:
        return orchestrator.debate_side(symbol, side)
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Debate could not load market data.') from exc


@router.post('/prefetch/{symbol}')
def prefetch_debate(symbol: str) -> dict:
    return orchestrator.prefetch_debate(checked_symbol(symbol))


@router.get('/debate-state/{symbol}')
def debate_state(symbol: str) -> dict:
    return orchestrator.debate_state(checked_symbol(symbol))


class MentionRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)


@router.post('/mention')
def debate_mention(request: MentionRequest) -> dict:
    symbol = mentioned_symbol(request.text)
    return orchestrator.prefetch_debate(symbol) if symbol else {"status": "idle", "symbol": None}


@router.post('/ask', response_model=VisualAnswer)
def ask(request: MentionRequest) -> VisualAnswer:
    if len(request.text) > 500:
        raise HTTPException(status_code=422, detail='Questions must be 500 characters or less')
    try:
        mandate = load_mandate()
        try:
            broker = get_broker() if mandate else None
        except HTTPException:
            broker = None
        return answer(request.text, mandate, broker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Market guidance is unavailable. Please retry.') from exc


class JudgeRequest(BaseModel):
    symbol: str
    bull_argument: str
    bear_argument: str


@router.post('/judge', response_model=TradeProposal)
def judge_request(request: JudgeRequest) -> TradeProposal:
    symbol = checked_symbol(request.symbol)
    if not request.bull_argument.strip() or not request.bear_argument.strip():
        raise HTTPException(status_code=422, detail='Both analyst arguments are required')
    try:
        return orchestrator.judge_debate(symbol, request.bull_argument, request.bear_argument)
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Judge could not create a proposal.') from exc


@router.get('/history/{symbol}')
def history(symbol: str) -> dict:
    symbol = checked_symbol(symbol)
    try:
        return {'symbol': symbol, 'bars': daily_history([symbol])[symbol], 'source': 'Alpaca / IEX'}
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Price history unavailable.') from exc


@router.get('/opportunities')
def opportunities(mandate: UserMandate = Depends(required_mandate), broker: IBroker = Depends(get_broker)) -> dict:
    try:
        from intelligence.data_feeds.market_data import WATCHLIST
        quotes = market_summary()['quotes']
        histories = daily_history(list(WATCHLIST))
        account = orchestrator.account_snapshot(broker)
        return {'method': '20-session return divided by average daily range; positive returns only',
                'candidates': rank_opportunities(quotes, histories, mandate, account),
                'source': 'Alpaca / IEX'}
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Opportunity screen unavailable.') from exc


@router.post('/voice/transcribe')
async def transcribe(recording: UploadFile = File(...)) -> dict:
    try:
        audio = await recording.read()
        return {"text": transcribe_audio(recording.filename or "question.webm", recording.content_type or "", audio)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail='Voice transcription is unavailable. Please retry.') from exc


class GuideRequest(BaseModel):
    prompt: str
    countries: str = "us"
    symbols: str = ""


@router.post('/guide', response_model=GuidePlan)
def guide(
    request: GuideRequest,
    mandate: UserMandate = Depends(required_mandate),
    broker: IBroker = Depends(get_broker),
) -> GuidePlan:
    if len(request.prompt) > 500:
        raise HTTPException(status_code=422, detail='Guide requests must be 500 characters or less')
    if not INVESTING_TERMS.search(request.prompt):
        return invalid_plan()
    try:
        from intelligence.data_feeds.market_data import WATCHLIST
        quotes = market_summary()['quotes']
        histories = daily_history(list(WATCHLIST))
        candidates = rank_opportunities(quotes, histories, mandate, orchestrator.account_snapshot(broker))
        news_symbols = request.symbols or ",".join(item["symbol"] for item in candidates[:5])
        news = sync_news(request.countries, news_symbols, force=False, limit=10)["articles"]
        return build_guide(request.prompt, candidates, histories, news)
    except Exception as exc:
        raise HTTPException(status_code=502, detail='The guided workspace is unavailable. Please retry.') from exc


class NewsSyncRequest(BaseModel):
    countries: str = "us"
    symbols: str = ""
    force: bool = False


@router.get('/news')
def news(countries: str = "us", symbols: str = "", limit: int = 20) -> dict:
    try:
        return cached_news(countries, symbols, limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post('/news/sync')
def news_sync(request: NewsSyncRequest) -> dict:
    try:
        return sync_news(request.countries, request.symbols, request.force, limit=10)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        cached = cached_news(request.countries, request.symbols, 20)
        if cached["articles"]:
            cached.update({"stale": True, "new_count": 0, "fetched_count": 0, "cache_hit": True})
            return cached
        raise HTTPException(status_code=502, detail='Market news is unavailable and no cached stories exist.') from exc


class ExecuteRequest(BaseModel):
    proposal: TradeProposal
    approved: bool = False


@router.post("/validate")
def validate(proposal: TradeProposal, mandate: UserMandate = Depends(required_mandate), broker: IBroker = Depends(get_broker)) -> dict:
    try:
        return {"verdict": orchestrator.review(proposal, mandate, broker), "mode": mandate.auto_execution_mode}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Risk review could not load the live account. No order was submitted.") from exc


@router.post("/execute")
def execute(request: ExecuteRequest, mandate: UserMandate = Depends(required_mandate), broker: IBroker = Depends(get_broker)) -> dict:
    try:
        return orchestrator.execute(request.proposal, mandate, broker, request.approved)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Paper order or live risk check failed. Check Alpaca before retrying.") from exc
