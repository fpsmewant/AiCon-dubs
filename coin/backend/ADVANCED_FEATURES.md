# Coin intelligence and learning

## Configuration

The local `.env` supplies `LIQUID_API_KEY`, `LIQUID_EMBEDDING_MODEL` and
`LIQUID_CHAT_MODEL`. The supplied OpenRouter credential is used with LiquidAI's
`liquid/lfm-2.5-embedding-350m:free` embedding model. Credentials and SQLite
databases are ignored by Git.

## Memory

Run `python -m intelligence.index_memory` from the backend directory to backfill
the cached news database, ticker descriptions and scored trades. The command
also prints the top matches for a technology query. Existing unchanged documents
reuse their stored vectors. SQLite uses WAL and indexes for document metadata
and pending trade observations. Similarity search uses cosine distance.

New Marketaux stories are embedded in the background. The API startup worker
backfills existing records and checks broker fills and exits every minute.
Each actual fill establishes the entry price and observation times. Historical
IEX minute bars supply a snapshot ending 30 minutes before the fill and another
ending 30 minutes after it. Bracket exit fills supply the realized outcome.
Unavailable bars or historical sentiment remain missing; they are not synthesized.
The 30-minute outcome is provisional and is replaced by the exit outcome.

Comparable losing setups lower the judge's confidence. This is an evidence-based
heuristic, not a trained predictive model. Missing snapshots do not count as
matching signals. Durable pending records are reconciled after a restart.

## Added API routes

- `POST /api/ask` with `{"text":"Should I invest $100 in Nvidia?"}` returns
  speech, ticker, budget, chart, merits, risks, a firewall result and a proposal.
- `POST /api/mention` with `{"text":"Nvidia"}` starts a background debate.
- `POST /api/prefetch/NVDA` starts or reuses the same cached debate.
- `GET /api/debate-state/NVDA` returns running, complete or failed status and
  analyst arguments as they finish. Cache entries expire after two minutes.

Existing guide, debate, mandate, validation and execution routes remain available.
Gemini runs the Bull analyst and Groq runs the Bear analyst, with OpenRouter
fallback. A click approving an order calls execution directly. Bounded autopilot
submits passing proposals after analysis. Both paths recheck the live firewall;
research-only mode never submits an order.

Dollar-sized proposals can use fractional quantities. Broker asset eligibility
and supported order combinations still apply; Coin retains the bracket order
contract. Tests mock broker submission and never place an order.
