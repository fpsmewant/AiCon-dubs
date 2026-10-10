# Coin

Coin is an AI-powered algorithmic trading and risk management platform for retail investors. It combines multi-agent market analysis with strict, capital-preservation-first risk controls and paper-trading execution.

## Project goals

- Analyze market conditions using Gemini and Groq through LangChain.
- Produce structured trade proposals with evidence, confidence, sizing, entry, and intended holding period.
- Route every proposal through a non-negotiable Risk Firewall before execution.
- Enforce user-defined allocation, position-size, stop-loss, daily-loss, and asset-exclusion rules.
- Keep account and portfolio state synchronized with the Alpaca Paper Trading API.
- Support Observe, Recommend & Approve, and Bounded Autopilot operating modes.

## Planned architecture

```text
coin/
├── frontend/                  # React/Next.js web dashboard
│   └── src/
│       ├── components/        # Charts, debate transcript, trade modals
│       ├── pages/             # Dashboard, settings, risk config, audit log
│       ├── services/          # Backend API clients
│       └── store/             # Live portfolio state
└── backend/                   # Python core engine and API
    ├── api/                   # REST endpoints
    ├── engine/                # Trade lifecycle orchestration
    ├── intelligence/          # Market data and multi-agent analysis
    ├── risk/                  # Risk Firewall and validators
    ├── execution/             # Broker abstraction and Alpaca adapter
    └── db/                    # Audit trail and application state
```

## Workflow

1. Sync account, positions, and market data from Alpaca.
2. Apply the user's capital allocation and hard risk boundaries.
3. Ask the Bull, Bear, and Judge agents to evaluate an opportunity.
4. Convert the Judge's result into a structured `TradeProposal`.
5. Run the proposal through every Risk Firewall validator.
6. Block invalid proposals; otherwise observe, request approval, or execute according to the selected operating mode.
7. Record proposals, decisions, orders, and outcomes for auditability.

## Demo scenarios

### Multi-agent stock debate

For an event such as an Nvidia earnings report, Gemini argues the upside case, Groq argues the downside case, and the Judge synthesizes both into a proposal or a no-trade recommendation. The dashboard will show the debate, evidence weights, rationale, size, entry, and intended holding period.

### Risk Firewall intervention

If a user allows a maximum loss of $50 per trade and an AI proposal requires a $100 stop-loss risk, the firewall must block the proposal even when the Judge has high confidence. User constraints always take precedence over AI conviction.

## Core technologies

- Intelligence: Gemini API, Groq API, LangChain
- Market data and execution: Alpaca Trading API in paper-trading mode
- Backend: Python with FastAPI or Flask
- Frontend: React or Next.js
- State and persistence: PostgreSQL and/or Redis

## Configuration

API credentials belong in a local environment file and must never be committed. The initial scaffold intentionally contains no secrets and no implementation code.

