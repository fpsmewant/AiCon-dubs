from intelligence.generators import TradeProposal, UserMandate


def validate(proposal: TradeProposal, mandate: UserMandate, account_info: dict) -> str | None:
    cost = proposal.qty * proposal.target_entry_price
    positions = account_info.get("positions", [])
    exposure = sum(abs(float(p.get("market_value", 0))) for p in positions)
    if exposure + cost > mandate.allocated_capital:
        return f"Allocation limit exceeded: current exposure ${exposure:.2f} + proposed ${cost:.2f} > ${mandate.allocated_capital:.2f}."
    if proposal.side.value == "sell" and account_info.get("shorting_enabled") is False:
        return "Short selling is disabled for this Alpaca account."
    if "buying_power" in account_info and cost > float(account_info["buying_power"]):
        return f"Buying power exceeded: proposed ${cost:.2f} > available ${float(account_info.get('buying_power', 0)):.2f}."
    return None
