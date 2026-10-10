"""Broker boundary, allowing risk and API code to be tested without a network."""

from abc import ABC, abstractmethod
from typing import Any

from intelligence.generators import TradeProposal


class IBroker(ABC):
    @abstractmethod
    def get_account(self) -> dict[str, Any]: ...

    @abstractmethod
    def get_positions(self) -> list[dict[str, Any]]: ...

    @abstractmethod
    def place_order(self, proposal: TradeProposal) -> dict[str, Any]: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> None: ...
