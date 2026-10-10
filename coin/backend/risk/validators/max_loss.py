from intelligence.generators import TradeProposal, UserMandate


def validate(proposal: TradeProposal, mandate: UserMandate, account_info: dict) -> str | None:
    if not proposal.qty.is_integer():
        return "Bracket orders require a whole-share quantity."
    if any(round(price, 2) != price for price in (proposal.target_entry_price, proposal.stop_loss_price, proposal.take_profit_price)):
        return "Bracket prices must be in whole cents."
    if proposal.side.value == "buy":
        if proposal.stop_loss_price >= proposal.target_entry_price or proposal.take_profit_price <= proposal.target_entry_price:
            return "Buy bracket must have stop loss below entry and take profit above entry."
        loss = (proposal.target_entry_price - proposal.stop_loss_price) * proposal.qty
    else:
        if proposal.stop_loss_price <= proposal.target_entry_price or proposal.take_profit_price >= proposal.target_entry_price:
            return "Sell bracket must have stop loss above entry and take profit below entry."
        loss = (proposal.stop_loss_price - proposal.target_entry_price) * proposal.qty
    if loss > mandate.max_loss_per_trade:
        return f"Per-trade loss limit exceeded: potential ${loss:.2f} > ${mandate.max_loss_per_trade:.2f}."
    daily_loss = float(account_info.get("daily_loss", 0))
    if daily_loss + loss > mandate.max_daily_loss:
        return f"Daily loss limit exceeded: current ${daily_loss:.2f} + potential ${loss:.2f} > ${mandate.max_daily_loss:.2f}."
    return None
