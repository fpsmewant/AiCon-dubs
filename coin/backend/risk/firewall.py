from intelligence.generators import FirewallVerdict, TradeProposal, UserMandate
from risk.validators import allocation, max_loss, position_size


class RiskFirewall:
    def validate(self, proposal: TradeProposal, mandate: UserMandate, account_info: dict) -> FirewallVerdict:
        reasons = [
            reason
            for validator in (allocation.validate, max_loss.validate, position_size.validate)
            if (reason := validator(proposal, mandate, account_info)) is not None
        ]
        if (proposal.bull_argument.startswith('OpenRouter bull analysis unavailable')
                or proposal.bear_argument.startswith('OpenRouter bear analysis unavailable')):
            reasons.append('Debate incomplete: both analyst responses are required before a paper order.')
        return FirewallVerdict(passed=not reasons, rejected_reasons=reasons, proposal=proposal)
