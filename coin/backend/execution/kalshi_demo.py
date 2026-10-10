"""Small, demo-only client for event-market prices and orders."""

import base64
import os
import time
import uuid
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


DEMO_URL = "https://external-api.demo.kalshi.co/trade-api/v2"
ALLOWED_URLS = {DEMO_URL, "https://demo-api.kalshi.co/trade-api/v2"}


class CoinBotDemoClient:
    def __init__(self):
        self.base_url = os.getenv("COINBOT_DEMO_BASE_URL", DEMO_URL).rstrip("/")
        if self.base_url not in ALLOWED_URLS:
            raise ValueError("CoinBot accepts demo endpoints only")
        self.key_id = os.getenv("COINBOT_DEMO_KEY_ID", "").strip()
        key_path = os.getenv("COINBOT_DEMO_PRIVATE_KEY_PATH", "").strip()
        if not self.key_id or not key_path:
            raise ValueError("CoinBot demo credentials are not configured")
        self.private_key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)

    def _request(self, method: str, path: str, *, params=None, payload=None, auth=True):
        if not path.startswith("/") or "?" in path:
            raise ValueError("Use an absolute API path and separate query parameters")
        headers = {}
        if auth:
            timestamp = str(int(time.time() * 1000))
            signed_path = "/trade-api/v2" + path
            message = f"{timestamp}{method}{signed_path}".encode()
            signature = self.private_key.sign(message, padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()), salt_length=hashes.SHA256().digest_size),
                hashes.SHA256())
            headers = {"KALSHI-ACCESS-KEY": self.key_id,
                       "KALSHI-ACCESS-TIMESTAMP": timestamp,
                       "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode()}
        response = requests.request(method, self.base_url + path, params=params, json=payload,
                                    headers=headers, timeout=(5, 12))
        response.raise_for_status()
        return response.json()

    def markets(self, status="open"):
        return self._request("GET", "/markets", params={"series_ticker": "KXBTC15M",
            "status": status, "limit": 100}, auth=False).get("markets", [])

    def market(self, ticker: str):
        return self._request("GET", f"/markets/{ticker}", auth=False)["market"]

    def balance(self):
        return self._request("GET", "/portfolio/balance")

    def positions(self, ticker: str):
        return self._request("GET", "/portfolio/positions", params={"ticker": ticker, "limit": 100})

    def order(self, *, ticker: str, outcome: str, action: str, count: int, yes_price: float):
        if outcome not in ("yes", "no") or action not in ("buy", "sell"):
            raise ValueError("Invalid outcome or action")
        if count < 1 or not 0.01 <= yes_price <= 0.99:
            raise ValueError("Invalid order quantity or price")
        side = "bid" if (outcome == "yes") == (action == "buy") else "ask"
        return self._request("POST", "/portfolio/events/orders", payload={
            "ticker": ticker, "side": side, "count": str(count),
            "price": f"{yes_price:.4f}", "time_in_force": "immediate_or_cancel",
            "reduce_only": action == "sell", "client_order_id": str(uuid.uuid4()),
            "self_trade_prevention_type": "taker_at_cross"})
