# QuantFlow — AI Trading Strategy Studio (MVP Phase 1)

A Claude-style chatbot that turns plain-English trading-strategy descriptions
into runnable backtests, parameter-optimized variants, and AI-filtered trade
sets — all served through a polished, dark-themed UI.

This codebase implements **Phase 1** of the architecture described in
`../quantflow_technical_architecture.docx`. Code generation, ML weights, and
the optimisation / AI filter logic stay **server-side**: the client only ever
receives JSON results, charts, and metric data.

```
┌──────────────────────────────────────────────────────────────────────────┐
│  QUANTFLOW PIPELINE                                                      │
│                                                                          │
│   USER PROMPT ──► PARSE ──► CONFIRM ──► BACKTEST ──► RESULTS             │
│                                            │                             │
│                                            ├──► STRATEGY FINDER          │
│                                            ├──► AI FILTER                │
│                                            ├──► PROS / CONS / NEXT STEPS │
│                                            └──► SAVE STRATEGY            │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## What's inside

```
quantflow/
├── backend/                       FastAPI + SQLite + state-machine orchestrator
│   ├── core/
│   │   ├── indicators/            EMA, SMA, WMA, RSI, MACD, Stochastic, ROC,
│   │   │                          ATR, Bollinger, Keltner, ADX, SuperTrend,
│   │   │                          VWAP, OBV  + a single REGISTRY
│   │   ├── patterns/              Heikin Ashi, candlesticks, S/R pivots
│   │   ├── strategy/
│   │   │   ├── base.py            StrategyBase + Signal/Position dataclasses
│   │   │   ├── templates.py       5 pre-built strategies (HA EMA cross,
│   │   │   │                      EMA cross, RSI mean-reversion, BB breakout,
│   │   │   │                      MACD trend)
│   │   │   └── registry.py        Template registry
│   │   ├── backtest/              Bar-by-bar engine + 20+ metrics
│   │   ├── optimizer/             Grid search + walk-forward validation
│   │   └── ai_filter/             LightGBM-loadable filter w/ heuristic fallback
│   ├── data/                      OHLCV loader (CSV-backed for MVP)
│   ├── api/
│   │   ├── main.py                FastAPI app
│   │   ├── db.py / models.py      SQLAlchemy (SQLite default; swap to Postgres
│   │   │                          via QUANTFLOW_DATABASE_URL)
│   │   ├── routes/                /conversations /strategies /catalog
│   │   ├── services/
│   │   │   ├── llm.py             Claude API client + heuristic offline mock
│   │   │   ├── orchestrator.py    State machine (PARSE → CONFIRM → BACKTEST → ...)
│   │   │   └── executor.py        Glue between parsed spec and core engine
│   │   └── prompts/               Jinja2 templates (versioned, server-side only)
│   ├── requirements.txt
│   └── run.py                     Local dev entry-point
│
└── frontend/                      Next.js 14 + Tailwind + Recharts
    ├── app/                       App-Router pages, layout, globals
    ├── components/
    │   ├── Sidebar.tsx            Conversations + saved strategies list
    │   ├── ChatPanel.tsx          Main thread, busy states, streaming-style UX
    │   ├── MessageBubble.tsx      Renders text + rich result cards
    │   ├── StrategyConfirmation.tsx Confirms parsed logic / lets user edit params
    │   ├── ResultsCards.tsx       BacktestCard / FinderCard / FilterCard / ImprovementsCard
    │   ├── EquityChart.tsx        Equity & drawdown charts (Recharts)
    │   ├── MetricsGrid.tsx        Metric tile grid + before/after compare rows
    │   ├── TradeTable.tsx         Trade log (collapsed last-12 + show all)
    │   ├── ActionButtons.tsx      Inline "Strategy Finder / AI Filter / Improve / Save" buttons
    │   └── Composer.tsx           Bottom input box, Enter to send
    ├── lib/
    │   ├── api.ts                 Typed fetch client (proxies /api → backend)
    │   ├── types.ts
    │   └── format.ts
    ├── tailwind.config.js         Custom palette (Claude-ish copper accent)
    └── package.json
```

---

## Quick start

### 1) Backend

Requires Python 3.10+.

```bash
cd quantflow/backend
pip install -r requirements.txt
python run.py
```

Server runs at `http://127.0.0.1:8000`. SQLite DB is auto-created at
`quantflow/quantflow.db` on first launch.

#### Optional environment variables

| Var | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | _(empty)_ | Switch from offline mock to Claude API |
| `ANTHROPIC_MODEL` | `claude-sonnet-4-5` | Model name passed to Anthropic SDK |
| `QUANTFLOW_LLM_MODE` | `auto` | `auto` / `claude` / `mock` |
| `QUANTFLOW_DATABASE_URL` | `sqlite:///quantflow.db` | Any SQLAlchemy URL (e.g. Postgres) |
| `QUANTFLOW_INITIAL_CAPITAL` | `100000` | Starting capital for backtests |
| `QUANTFLOW_POSITION_SIZE` | `1.0` | Units per trade (point-PnL) |
| `QUANTFLOW_DATA_LIMIT` | `20000` | Max bars per backtest run |
| `QUANTFLOW_ALLOWED_ORIGINS` | `http://localhost:3000` | CORS list |

> The chatbot works **fully offline** with the heuristic mock parser. Plug in
> a Claude key any time to upgrade strategy parsing / summary / improvement
> generation to the LLM.

### 2) Frontend

Requires **Node.js 18+** (install from [nodejs.org](https://nodejs.org/)).

```bash
cd quantflow/frontend
npm install
npm run dev
```

Open `http://localhost:3000`. The Next.js dev server automatically proxies
`/api/*` to the FastAPI server on `:8000`.

---

## How to use it

1. Type a strategy in plain English in the bottom composer:

   - *"Heikin Ashi EMA 9 / 21 / 55 cross on XAUUSD 5m"*
   - *"RSI mean-reversion 14, buy below 30, sell above 70 on XAUUSD"*
   - *"MACD 12 26 9 with 200-EMA trend filter on XAUUSD 15m"*
   - *"Bollinger 20 / 2 breakout strategy"*

2. QuantFlow shows a **Strategy Confirmation** card with the parsed entry /
   exit rules, indicators, parameters, and instrument / timeframe. Click
   **Run Backtest** (or **Edit Parameters** to tweak first).

3. The **Backtest Card** appears with:
   - 12-tile metrics grid (return, Sharpe, drawdown, profit factor, win rate, …)
   - Equity curve + drawdown chart
   - Collapsible trade table
   - Action buttons:
     - **Run Strategy Finder** → grid-search the parameter space (with
       walk-forward validation across 3 splits)
     - **Apply AI Filter** → score each entry on context features and drop
       low-conviction trades; shows before/after side-by-side
     - **Get Pros / Cons & Improvements** → critique + ranked next-steps with
       one-click "Apply & re-run" buttons for basic filters
     - **Save Strategy** → persists everything to the DB

4. The left sidebar tracks every conversation (auto-titled from the first
   message) plus all saved strategies with status badges (`draft`,
   `backtested`, `optimized`, `filtered`).

---

## Wiring your own existing IP

### Bring in your real strategies

The pre-built templates in `backend/core/strategy/templates.py` are the
existing rule-based strategies (Heikin Ashi EMA cross etc.). To register
additional ones from your wider `marketapi_data_fetcher/.../strategies`:

```python
from backend.core.strategy import register_strategy, StrategyBase

class MyAwesomeStrategy(StrategyBase):
    name = "my_awesome"
    description = "..."
    default_params = {...}
    param_ranges = {...}
    def prepare(self, df): ...
    def on_bar(self, i, row, df): ...

register_strategy(MyAwesomeStrategy)
```

Then add it to the indicator/template list shown in the parser prompt
(automatic, since `list_strategy_templates()` is dynamic).

### Plug in your trained AI Filter models

`AIFilter` accepts `model_path` and `scaler_path` to load a pickled scikit-
learn / LightGBM classifier. To use the existing pickled models from
`Optimization_Strategies/notebook/Heikin Ashi/heikin_ashi_model_4hr_v7_weighted.pkl`,
edit `executor.execute_ai_filter` (or pass paths via the route payload) and
update `core/ai_filter/filter.py::FEATURE_COLUMNS` to match the feature
schema your model was trained on.

### Swap SQLite → Postgres + TimescaleDB (for production)

Set `QUANTFLOW_DATABASE_URL=postgresql://user:pass@host:5432/quantflow`. The
ORM models in `backend/api/models.py` are intentionally compatible with the
schema in §5 of the architecture document — only `OHLCV` storage needs an
extra hypertable migration when you upgrade.

---

## What's intentionally NOT in MVP Phase 1

These are tracked for **Phase 1.5 / 2** in the architecture doc:

- LLM-generated *new* strategy classes (Phase 1 picks the closest registered
  template; the `code_generator.jinja2` prompt is staged for Phase 2 sandbox
  execution)
- Telegram notifications (Section 6.2 of the doc; ~2 days of work)
- Broker deployment (Section 6.3; OrderRouter + paper / live adapters)
- User auth / multi-tenant (the schema is in place but no NextAuth wiring
  yet)
- TimescaleDB hypertable migration
- Daily OHLCV cron ingestion (currently CSV-backed)

---

## State machine

The orchestrator (`api/services/orchestrator.py`) implements the architecture
doc's state machine almost verbatim:

```
GREETING ──► AWAITING_CONFIRM ──► HAS_BACKTEST ──► HAS_OPTIMIZED
                  │                    │                │
                  │                    └──► HAS_FILTERED
                  └── (re-parse on new request) ──┘
```

Every transition writes one or more `Message` rows; the frontend just renders
whatever comes back. To add a new step (e.g. "DEPLOY"), add a `_run_*_step`
function and a new `action` string handled in `handle_message()`.

---

## IP protection (Section 4 of the doc)

- The full Python strategy code is generated server-side and stored in
  `Strategy.strategy_code` — never sent to the client.
- The AI Filter pickled model file path is server-side only; the client only
  receives feature-importance percentages and per-trade scores.
- The Strategy Finder loops are pure server compute; the client only sees
  ranked param dictionaries + metrics.
- All prompt templates live in `backend/api/prompts/` and never leave the
  server.

---

## License

Proprietary — internal QuantFlow / TradeXpert codebase.
