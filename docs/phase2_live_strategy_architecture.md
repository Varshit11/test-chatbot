# Phase 2 — Live Strategy Execution at Scale

**Status:** Planning. No code written for this. Reviewing this doc is the pre-requisite for any implementation.

**Author context:** today, the user's setup is:
- Cron jobs run a Python script every N minutes (per-symbol, per-timeframe).
- The script pulls bars (Finnhub), computes features, runs the strategy, and **POSTs a signal** to a Flask endpoint (`signal_server.py:30 /update_signal`).
- A separate MQL5 script polls `GET /get_signal` and places the trade.

**Why this doesn't scale.** This pattern is "one process per (user × strategy × symbol)" — one Telegram channel + one Render dyno worth. With 100 users each owning one strategy, that's potentially 100s–1000s of cron jobs all hitting Finnhub on their own schedule, recomputing the same indicators on the same bars, and writing into a single shared `signal_server` keyed by symbol. We need to invert: one ingestion / feature pipeline (already being built in Phase 1), and a *fan-out* that evaluates many strategies on each fresh bar.

---

## Target architecture (single page)

```
                      ┌──────────────────────────┐
                      │  Phase-1 Ingest Pipeline │
                      │  (already implemented)   │
                      │   Finnhub → 1m parquet   │
                      │   resample → 5m / 15m… │
                      │   features → parquet     │
                      └────────────┬─────────────┘
                                   │ on bar-close event
                                   ▼
                       ┌───────────────────────┐
                       │  Bar-close dispatcher │
                       │  (publishes a "5m bar │
                       │  closed for XAUUSD"   │
                       │  event to a queue)    │
                       └───────────┬───────────┘
                                   │ event
                                   ▼
                  ┌────────────────────────────────────┐
                  │  Strategy Worker Pool (N workers)  │
                  │  Each worker picks an event,       │
                  │  loads the strategy classes that   │
                  │  *subscribe* to that bar, runs     │
                  │  on_bar(), emits zero or more      │
                  │  Signal records.                   │
                  └─────────────────┬──────────────────┘
                                    │ signal
                                    ▼
                          ┌────────────────────┐
                          │  Signal Bus / DB   │
                          │  (Postgres table   │
                          │  + Redis pub/sub)  │
                          └────┬─────────┬─────┘
                               │         │
            ┌──────────────────┘         └──────────────────┐
            ▼                                                ▼
   ┌──────────────────┐                            ┌──────────────────┐
   │ Public Signal API│  ← MT5 / mobile / webhook  │ Notification fan-│
   │ /v1/signals/poll │     poll OR subscribe      │ out (Telegram,   │
   │ /v1/signals/stream│                           │ email, push)     │
   └──────────────────┘                            └──────────────────┘
```

The key claim: **the cost driver is bars and features, not strategies.** Once Phase 1 stores the bar + features once per (symbol, TF), every additional user / strategy is just a new row in a `subscriptions` table and a few microseconds of `on_bar()` evaluation.

---

## Concrete components

### 1. Data layer (already done in Phase 1)
- `data/ohlcv/{SYMBOL}/{tf}.parquet` — canonical bars.
- `data/prebuilt_features/{SYMBOL}_{tf}_smc.parquet` — features.
- Owner: ingest runner (`backend/ingest/runner.py`).

No change here for Phase 2.

### 2. Bar-close events
After the ingest runner upserts a higher-TF bar, it should publish a tiny event like:
```json
{"symbol": "XAUUSD", "timeframe": "5m", "close_ts": "2026-05-04T07:35:00Z"}
```
Targets, in increasing maturity:
- **Local dev / single VM** → in-process queue (`asyncio.Queue` or `multiprocessing.Queue`).
- **Render / single-region prod** → Redis pub/sub (`SUBSCRIBE bar:5m:XAUUSD`) or Redis Streams (`XADD bar.events …`). Streams are preferred — they give you replay, consumer groups (one event delivered to one worker per group), and durability without standing up Kafka.
- **AWS-native multi-AZ** → **EventBridge** (rule per `(symbol, tf)`) → **SQS** queue per worker pool → workers. EventBridge gives you cross-account fan-out and a built-in dashboard. Keep one queue per *priority class* (real-money strategies vs. paper) so a slow strategy never head-of-lines an HFT one.

### 3. Strategy registry & subscription table

```sql
-- live_strategies: a saved (parsed_strategy + parameters + user_id) bundle
create table live_strategies (
    id              uuid primary key,
    user_id         uuid not null,
    name            text not null,
    instrument      text not null,    -- "XAUUSD"
    timeframe       text not null,    -- "5m"
    parsed_strategy jsonb not null,   -- the same parsed-spec the chatbot already produces
    generated_python text,            -- nullable; required when implementation_mode == 'generated_class'
    is_active       boolean not null default true,
    created_at      timestamptz default now(),
    last_signal_at  timestamptz
);

create index live_strategies_active on live_strategies (instrument, timeframe) where is_active;

-- signals: history + audit
create table signals (
    id              bigserial primary key,
    strategy_id     uuid not null references live_strategies(id),
    bar_close_ts    timestamptz not null,
    side            text not null,    -- "buy" | "sell" | "exit"
    entry_price     numeric,
    sl              numeric,
    tp              numeric,
    reason          text,
    delivered_at    timestamptz,
    payload         jsonb            -- raw signal record for the consumer
);
create index signals_strategy_bar on signals (strategy_id, bar_close_ts desc);
```

Every `on_bar()` invocation that returns a non-null `Signal` writes a row here. **The signals table is the single source of truth** — every consumer (MT5 polling, push-notification worker, future REST API) reads from it. `signal_server.py`'s in-memory dict is not durable enough at scale; it goes away.

### 4. Strategy worker pool

A worker process:
1. Receives an event `{symbol, timeframe, close_ts}`.
2. Queries `select id, parsed_strategy, generated_python from live_strategies where instrument=$1 and timeframe=$2 and is_active`.
3. For each row: load + cache the `StrategyBase` subclass (compile generated Python *once* per strategy id; reload only when `parsed_strategy.updated_at` changes), instantiate with the saved params, slice the bars/features up to `close_ts`, call `strategy.on_bar(...)`.
4. If a `Signal` comes back, insert into `signals` and PUBLISH on `signals:{user_id}` channel.

Workers are **stateless** — the only state is the strategy-class compile cache, which is rebuildable. So you scale by `N_workers = ceil(strategies_per_bar / latency_budget)`. With 100 users and 5m bars, even one worker handles it; the design is here so we can grow.

**Hot-reload**: when the chatbot saves an edited strategy, it bumps `parsed_strategy.updated_at`. Workers compare on next dispatch and recompile. No restart needed.

### 5. Consumer surface (how MT5 / mobile / webhooks see signals)

- **REST**: `GET /v1/signals?since=<ts>&strategy_id=...` returns recent signals. MT5 polls this every minute.
- **WebSocket / SSE**: `GET /v1/signals/stream?strategy_id=...` keeps a persistent connection and pushes each new signal. Lower latency, lower load. Use this once we have non-MT5 clients.
- **Webhook**: per-strategy "on signal, POST to URL" hook for users who want to integrate with their own broker bridge.
- **Telegram / push**: a notification worker subscribes to `signals:*` and dispatches per the user's notification preferences.

The `/get_signal` endpoint in today's `signal_server.py` becomes a thin compatibility shim that wraps `/v1/signals?strategy_id=<MT5-mapped-id>&latest=1`. Old MT5 scripts keep working.

### 6. Sandboxing user-generated Python

This is the *single* hardest problem. `dynamic_loader.py` already runs strategy code in a restricted exec namespace (no imports, AST-validated, allowlisted builtins). For multi-tenant prod that's not enough — a runaway loop or a 5GB DataFrame can DoS a worker.

Hardening checklist for Phase 2:
- **Per-call CPU budget**: run `on_bar` on a worker thread with `signal.SIGALRM` (Linux) / `threading.Timer + raise` fallback. Kill if it exceeds, say, 250 ms.
- **Per-process memory ceiling**: cgroups (k8s `resources.limits.memory`) or `resource.setrlimit(RLIMIT_AS, …)`. If a strategy frequently hits the ceiling, the system disables it and pings the user.
- **No cross-strategy state**: each compiled class is reset between bars. Already enforced by the architecture.
- **Failure isolation**: any exception inside `on_bar` is caught, the failure is logged into `signals` with `side='error'`, the strategy is *not* disabled (could be transient data) but a sliding-window error rate (>10% of bars in last hour) triggers auto-disable + a notification to the user.

### 7. Latency and ordering guarantees

- **Latency target**: signal is in the DB ≤ 5 seconds after the bar closes on Finnhub. That's plenty for 5m+ strategies. Sub-second triggers (1m scalping) need a separate hot-path that bypasses parquet — out of scope for Phase 2.
- **Ordering**: events are processed in `(symbol, tf)` order via a single consumer-group partition per `(symbol, tf)` (Redis Streams' or SQS FIFO's `MessageGroupId` = `f"{symbol}:{tf}"`). Within a partition, signals are linear. Across partitions, no global order — fine, strategies don't span symbols/TFs.

### 8. Cost / infra mapping (AWS, since the user mentioned AWS)

| Component                  | Cheapest landing zone          | Production landing zone           |
|----------------------------|--------------------------------|-----------------------------------|
| Ingest runner              | EC2 t3.small + cron            | ECS Fargate (1 task) + EventBridge cron |
| Bar-close dispatcher       | (in-process)                   | EventBridge rule on parquet write |
| Parquet store              | Local disk on EC2              | S3 (versioned, lifecycle to Glacier) |
| Strategy worker pool       | EC2, supervisord, N processes  | ECS Fargate, target tracking on SQS depth |
| Signals DB                 | RDS Postgres db.t3.micro       | RDS Multi-AZ + read replica       |
| Pub/sub                    | Redis on the same EC2          | ElastiCache Redis or SNS          |
| Public REST/WS surface     | The existing FastAPI box       | API Gateway HTTP + ECS service    |

For 100 users / 1 symbol / 5m bars, the cheapest column is genuinely enough — single small EC2 + RDS micro is ~$30/month. Going to the production column happens only when you cross ~5k strategies or onboard users from regulated jurisdictions.

---

## Open questions (need user decisions before any code)

1. **Hosting**: Render (current), pure AWS, or hybrid (Render for frontend, AWS for ingest + workers)?
2. **Signal latency SLA**: is 5s post-bar-close acceptable, or do we need sub-second for scalping?
3. **Broker integrations**: only MT5 for now, or also direct broker APIs (OANDA, IBKR)?
4. **Multi-region**: one region (us-east-1) sufficient, or do EU/APAC users need lower latency?
5. **Paper vs. live**: do we run a paper-trade ledger inside the platform (`positions` table updated from signals) or just emit signals and let the broker side reconcile?
6. **User-generated code policy**: do we host arbitrary user Python on shared workers (today's pattern, with the sandbox), or move to per-user containers (k8s pod per user, cleaner isolation, ~10x cost)?

Each answer trims one or two of the boxes above. Let's settle these before I start writing modules.

---

## Migration path from today's setup

1. Phase 1 (done): canonical ingest. Both the chatbot and existing `marketapi_data_fetcher` cron scripts can read from `data/ohlcv/...` instead of Finnhub directly. Cuts API calls, keeps existing scripts running.
2. Add `live_strategies` and `signals` tables to the chatbot's SQLite (or upgrade to Postgres). The "Save strategy" button in the UI already exists — this just puts it on a queryable schedule.
3. Build a single-process worker that polls every 60s for "new bars since last poll" and runs each active strategy. No Redis / SQS yet. **This alone replaces all per-strategy cron jobs.**
4. Add the `/v1/signals` REST endpoint + a tiny MT5 EA-compatibility shim that mimics today's `/get_signal`. Cut over one strategy, verify, then move the rest.
5. Once #3 is healthy at ~50 strategies, swap the in-process worker for SQS + N ECS workers. No code change inside the worker — only the dispatch glue.

Steps 2–4 are days of work each, not weeks. Step 5 is the AWS lift.
