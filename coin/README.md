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

## Run the Alpaca paper-trading connectivity test

### Backend Setup

1. Open `coin/backend/.env.example`, copy it to `coin/backend/.env`, and replace:
   - `ALPACA_API_KEY` with the **paper** API key from the Alpaca dashboard.
   - `ALPACA_SECRET_KEY` with the matching **paper** secret key.
   - Keep `ALPACA_BASE_URL=https://paper-api.alpaca.markets`.

2. From the `coin/backend` directory, set up your Python environment and dependencies:

   **Windows (PowerShell):**
   ```powershell
   python -m pip install -r requirements.txt
   ```

   **Linux:**
   Create a virtual environment (`.venv`), activate it, and install the dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Start the application backend:
   ```bash
   python3 -m uvicorn main:app --reload
   ```
   *(Windows alternative: `python -m uvicorn main:app --reload`)*

4. Open `http://127.0.0.1:8000`. The page loads the account cash/equity and has a **Buy paper stock** button. It submits a small market order to Alpaca's paper account and refreshes the account values.

The API keys must be entered only in `coin/backend/.env`; do not put them in frontend files or commit that file. This test places an order in the paper account, not the live account. Buying stock changes cash and positions; Alpaca does not provide a normal "add money" deposit action through this demo endpoint.

### Frontend Setup

To start the user interface dashboard on port 3000, navigate to the frontend folder, install the Next.js dependencies, and run the development environment:

**Linux / Windows:**
```bash
cd coin/frontend
npm install
npm run dev
```
*(Once running, open `http://localhost:3000` in your web browser.)*
