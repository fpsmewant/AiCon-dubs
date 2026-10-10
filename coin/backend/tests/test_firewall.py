from intelligence.generators import TradeProposal, UserMandate
from engine.orchestrator import execute
from execution.broker_adapter import IBroker
from risk.firewall import RiskFirewall


def mandate(**overrides):
    values = dict(
        allocated_capital=10_000,
        risk_style="balanced",
        max_loss_per_trade=100,
        max_daily_loss=300,
        max_position_size=2_000,
        auto_execution_mode="recommend_approve",
    )
    return UserMandate(**(values | overrides))


def proposal(**overrides):
    values = dict(
        symbol="AAPL", side="buy", qty=10, target_entry_price=100,
        stop_loss_price=95, take_profit_price=110,
        bull_argument="Possible upside.", bear_argument="Gap risk.",
        judge_summary="Cautious trade.", confidence_score=0.6,
        estimated_upside_pct=10, estimated_downside_pct=5,
    )
    return TradeProposal(**(values | overrides))


def test_safe_trade_passes():
    result = RiskFirewall().validate(proposal(), mandate(), {"buying_power": 5000, "daily_loss": 0, "positions": []})
    assert result.passed
    assert result.rejected_reasons == []


def test_unavailable_analyst_blocks_execution_even_with_manual_approval():
    broker = FakeBroker()
    trade = proposal(bull_argument='OpenRouter bull analysis unavailable or rate limited.')
    result = execute(trade, mandate(), broker, approved=True)
    assert result['status'] == 'rejected'
    assert any('Debate incomplete' in reason for reason in result['verdict'].rejected_reasons)
    assert broker.orders == []


def test_every_limit_rejects_with_specific_reason():
    result = RiskFirewall().validate(
        proposal(qty=30, stop_loss_price=90),
        mandate(allocated_capital=2500, max_position_size=2000, max_loss_per_trade=100, max_daily_loss=150),
        {"buying_power": 1000, "daily_loss": 40, "positions": []},
    )
    assert not result.passed
    assert any("Allocation limit" in reason for reason in result.rejected_reasons)
    assert any("Per-trade loss" in reason for reason in result.rejected_reasons)
    assert any("Position size" in reason for reason in result.rejected_reasons)


def test_daily_loss_blocks_even_when_trade_loss_is_within_limit():
    result = RiskFirewall().validate(proposal(), mandate(max_daily_loss=60), {"daily_loss": 20, "buying_power": 5000})
    assert not result.passed
    assert any("Daily loss" in reason for reason in result.rejected_reasons)


def test_wrong_side_bracket_is_blocked():
    result = RiskFirewall().validate(proposal(stop_loss_price=105), mandate(), {"buying_power": 5000})
    assert not result.passed
    assert any("Buy bracket" in reason for reason in result.rejected_reasons)


def test_existing_exposure_counts_toward_limits():
    result = RiskFirewall().validate(proposal(), mandate(max_position_size=1500), {"positions": [{"symbol": "AAPL", "market_value": 600}], "buying_power": 5000})
    assert not result.passed
    assert any("Position size" in reason for reason in result.rejected_reasons)


class FakeBroker(IBroker):
    def __init__(self):
        self.orders = []

    def get_account(self):
        return {"buying_power": 5000, "daily_loss": 0}

    def get_positions(self):
        return []

    def place_order(self, trade):
        self.orders.append(trade)
        return {"id": "paper-order-1"}

    def cancel_order(self, order_id):
        pass


def test_manual_approval_and_observe_cannot_bypass_firewall():
    broker = FakeBroker()
    assert execute(proposal(), mandate(), broker)["status"] == "awaiting_approval"
    assert broker.orders == []
    assert execute(proposal(), mandate(auto_execution_mode="observe"), broker, approved=True)["status"] == "observed"
    assert broker.orders == []
    assert execute(proposal(qty=30), mandate(), broker, approved=True)["status"] == "rejected"
    assert broker.orders == []
    assert execute(proposal(), mandate(), broker, approved=True)["status"] == "submitted"
    assert len(broker.orders) == 1
