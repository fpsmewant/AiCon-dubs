from intelligence.generators import TradeProposal, UserMandate


def validate(proposal: TradeProposal, mandate: UserMandate, account_info: dict) -> str | None:
    value = proposal.qty * proposal.target_entry_price
    existing = sum(abs(float(p.get("market_value", 0))) for p in account_info.get("positions", []) if p.get("symbol") == proposal.symbol)
    if existing + value > mandate.max_position_size:
        return f"Position size limit exceeded: existing ${existing:.2f} + proposed ${value:.2f} > ${mandate.max_position_size:.2f}."
    return None
