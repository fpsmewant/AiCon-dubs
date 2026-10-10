from pathlib import Path
from contextlib import asynccontextmanager
from threading import Event, Thread

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).with_name(".env"))

from api.routes import router  # noqa: E402 - load credentials before importing adapters
from api.coinbot import router as coinbot_router

@asynccontextmanager
async def lifespan(app):
    from engine.orchestrator import sync_learning
    from intelligence.index_memory import index_database, index_trade_outcomes
    stop = Event()
    def worker():
        try:
            index_database()
        except Exception:
            pass
        while not stop.is_set():
            try:
                sync_learning()
                index_trade_outcomes()
            except Exception:
                pass
            stop.wait(60)
    thread = Thread(target=worker, daemon=True, name='coin-learning')
    thread.start()
    from engine.coinbot import run as run_coinbot
    bot_thread = Thread(target=run_coinbot, args=(stop,), daemon=True, name='coinbot-stocks')
    bot_thread.start()
    yield
    stop.set()


app = FastAPI(title="Coin Paper Trading API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(router)
app.include_router(coinbot_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "Coin Paper Trading API", "dashboard": "http://localhost:3000"}
