"""ConversationOrchestrator — the brain.

Implements the state-machine described in the architecture doc §3.1:

    USER_INPUT
        → PARSE_STRATEGY
        → CONFIRM_LOGIC
        → COLLECT_PARAMS (if needed)
        → EXECUTE_BACKTEST → SHOW_RESULTS
        → [STRATEGY_FINDER] → [AI_FILTER]
        → SAVE_STRATEGY

Each transition emits 0..N assistant Messages that the frontend renders. The
orchestrator never returns code or proprietary internals — only data.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import logging

from sqlalchemy.orm import Session

from ..config import CONVERSATION_HISTORY_MESSAGES
from ..models import Conversation, Message, Strategy
from . import llm as llm_svc
from .executor import execute_backtest, execute_strategy_finder, execute_ai_filter

logger = logging.getLogger(__name__)


# state names
S_GREETING = "GREETING"
S_AWAITING_CONFIRM = "AWAITING_CONFIRM"
S_HAS_BACKTEST = "HAS_BACKTEST"
S_HAS_OPTIMIZED = "HAS_OPTIMIZED"
S_HAS_FILTERED = "HAS_FILTERED"


def _msg(conv: Conversation, role: str, content: str, msg_type: str = "text",
         meta: Optional[Dict[str, Any]] = None) -> Message:
    m = Message(
        conversation_id=conv.id,
        role=role,
        content=content,
        msg_type=msg_type,
        meta=meta or {},
    )
    return m


def _set_context(conv: Conversation, **patch) -> None:
    ctx = dict(conv.context or {})
    ctx.update(patch)
    conv.context = ctx


def _trim_context_for_storage(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """We keep heavy results in `Conversation.context` so the frontend can
    re-derive any view, but cap how much we store to avoid bloat."""
    out = dict(ctx)
    bt = out.get("backtest_result")
    if bt and isinstance(bt, dict):
        # already slimmed by executor; nothing more to do
        pass
    return out


_INTENT_PATTERNS: List[Tuple[str, List[str]]] = [
    ("run_finder", [
        "strategy finder", "run finder", "run the finder", "find best params",
        "param sweep", "parameter sweep", "grid search", "optimize",
        "optimization", "tune params", "tune parameters", "finder",
    ]),
    ("run_filter", [
        "ai filter", "apply ai filter", "apply filter", "ml filter",
        "run filter", "filter trades", "filter the trades", "ai-filter",
        "filter",
    ]),
    ("improve", [
        "pros and cons", "pros & cons", "pros cons", "improvement", "improvements",
        "improve", "review", "critique", "feedback", "what should i improve",
    ]),
    ("save", [
        "save", "save it", "save this", "save strategy", "save the strategy",
        "save this one", "bookmark",
    ]),
    ("confirm", [
        "run backtest", "run the backtest", "backtest", "run it", "go ahead",
    ]),
]


def _infer_action_from_text(user_text: str, *, has_backtest: bool) -> Optional[str]:
    """Cheap intent detector for plain-text shortcuts. Only matches when the
    user message is short and clearly action-like — anything longer (which
    likely describes a strategy or refinement) falls through to the parser."""
    s = (user_text or "").strip().lower()
    if not s:
        return None
    # Anything over ~6 words is probably a strategy description, not a command.
    if len(s.split()) > 6:
        return None
    for action_id, patterns in _INTENT_PATTERNS:
        for p in patterns:
            if p == s or p in s:
                # Some actions only make sense after a backtest exists.
                if action_id in {"run_finder", "run_filter", "improve", "save"} and not has_backtest:
                    return None
                return action_id
    return None


def _action_buttons_for_backtest(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Strategy Finder works for every strategy now that we always emit a
    # generated_class with default_params (so the previous "templates only"
    # guard is gone — keep the button on every backtest card).
    return [
        {"id": "run_finder", "label": "Run Strategy Finder", "icon": "search"},
        {"id": "run_filter", "label": "Apply AI Filter", "icon": "sparkles"},
        {"id": "improve", "label": "Get Pros / Cons & Improvements", "icon": "lightbulb"},
        {"id": "save", "label": "Save Strategy", "icon": "save"},
    ]


def _action_buttons_for_optimized(parsed: Dict[str, Any], *, best_beats_original: bool = True) -> List[Dict[str, Any]]:
    """Action buttons after a Strategy Finder run.

    When the search found at least one combo that beats the original on the
    chosen objective, we offer to apply those params and to AI-filter the
    optimized version. When the original was already best, applying the
    "best" params is a no-op and "AI filter on optimized" misleads the user —
    so we offer the AI filter on the **original** strategy instead.
    """
    if best_beats_original:
        return [
            {"id": "apply_best_params", "label": "Apply Best Params & Re-Backtest", "icon": "check"},
            {"id": "run_filter", "label": "Apply AI Filter on Optimized", "icon": "sparkles"},
            {"id": "improve", "label": "Get Improvements", "icon": "lightbulb"},
            {"id": "save", "label": "Save Strategy", "icon": "save"},
        ]
    return [
        {"id": "run_filter", "label": "Apply AI Filter on Original Strategy", "icon": "sparkles"},
        {"id": "improve", "label": "Get Improvements", "icon": "lightbulb"},
        {"id": "save", "label": "Save Strategy", "icon": "save"},
    ]


def _action_buttons_for_filtered() -> List[Dict[str, Any]]:
    return [
        {"id": "improve", "label": "Get Improvements", "icon": "lightbulb"},
        {"id": "save", "label": "Save Strategy", "icon": "save"},
    ]


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #


def handle_message(
    db: Session,
    conv: Conversation,
    user_text: str,
    action: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> List[Message]:
    """
    Process a single user turn and return the list of NEW assistant messages
    appended to the conversation. Caller is responsible for committing.
    """
    # Append user message
    user_msg = _msg(conv, "user", user_text, "text", meta={"action": action})
    db.add(user_msg)

    out: List[Message] = []
    # If no action was clicked, see if the user typed a shortcut for one of
    # the existing actions ("finder", "ai filter", "save", etc.) — use it
    # ONLY when there's already a parsed strategy in context, otherwise let
    # it fall through to the parser as a new strategy request.
    has_strategy = bool((conv.context or {}).get("parsed_strategy"))
    has_backtest = bool((conv.context or {}).get("backtest_result"))
    if action is None and has_strategy:
        inferred = _infer_action_from_text(user_text, has_backtest=has_backtest)
        if inferred:
            action = inferred
    try:
        if action == "confirm" and conv.state == S_AWAITING_CONFIRM:
            out.extend(_run_backtest_step(conv))
        elif action == "edit_params" and conv.state == S_AWAITING_CONFIRM:
            out.extend(_apply_edits_and_rerun(conv, payload or {}))
        elif action == "run_finder":
            out.extend(_run_finder_preview_step(conv))
        elif action == "confirm_run_finder":
            out.extend(_run_finder_step(conv, payload or {}))
        elif action == "apply_best_params":
            out.extend(_apply_best_params_step(conv))
        elif action == "run_filter":
            out.extend(_run_filter_step(conv))
        elif action == "improve":
            out.extend(_run_improvements_step(conv))
        elif action == "save":
            out.extend(_run_save_step(db, conv))
        else:
            # treat as new strategy request → re-parse
            out.extend(_parse_step(db, conv, user_text, user_msg))
    except Exception as e:
        logger.exception("orchestrator failure")
        out.append(_msg(conv, "assistant",
                        f"Sorry — I hit an error processing that: `{e}`. "
                        f"You can rephrase your request or try again.",
                        "text", {"error": str(e)}))

    for m in out:
        db.add(m)

    conv.context = _trim_context_for_storage(conv.context or {})
    conv.updated_at = datetime.utcnow()
    return out


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


def _parse_step(
    db: Session,
    conv: Conversation,
    user_text: str,
    user_msg: Message,
) -> List[Message]:
    db.flush()
    prior = (
        db.query(Message)
        .filter(Message.conversation_id == conv.id, Message.id != user_msg.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    cap = CONVERSATION_HISTORY_MESSAGES
    if len(prior) > cap:
        prior = prior[-cap:]
    lines: List[str] = []
    for m in prior:
        c = (m.content or "").strip()
        if not c:
            continue
        role_lbl = "User" if m.role == "user" else f"Assistant[{m.msg_type}]"
        lines.append(f"{role_lbl}: {c[:8000]}")
    transcript = "\n\n".join(lines)

    prior_spec = (conv.context or {}).get("parsed_strategy")
    parsed = llm_svc.parse_strategy(
        user_text,
        conversation_context=transcript or None,
        prior_spec=prior_spec,
    )
    _set_context(conv, parsed_strategy=parsed)

    if not conv.title or conv.title == "New Strategy":
        conv.title = _make_title(parsed)

    # Confirmation card
    confirm_meta = {
        "kind": "strategy_confirmation",
        "parsed": parsed,
        "actions": [
            {"id": "confirm", "label": "Run Backtest", "icon": "play"},
            {"id": "edit", "label": "Edit Parameters", "icon": "edit"},
        ],
    }

    strat_label = _strategy_display_name(parsed)
    summary = (parsed.get("summary") or "").strip()
    body = (
        f"**{strat_label}** on **{parsed['instrument']} {parsed['timeframe']}**"
        + (f"\n\n{summary}" if summary else "")
    )
    msgs: List[Message] = [_msg(conv, "assistant", body, "strategy_confirmation", confirm_meta)]

    if parsed.get("needs_clarification") and parsed.get("questions"):
        q_text = "Before I run anything, could you clarify:\n\n" + "\n".join(
            f"- {q}" for q in parsed["questions"]
        )
        msgs.append(_msg(conv, "assistant", q_text, "text"))

    conv.state = S_AWAITING_CONFIRM
    return msgs


def _run_backtest_step(conv: Conversation) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy")
    if not parsed:
        return [_msg(conv, "assistant", "I don't have a parsed strategy yet — please describe one first.")]

    try:
        bt = execute_backtest(parsed)
    except Exception as e:
        logger.exception("backtest failed")
        return [_msg(conv, "assistant",
                     f"⚠️ Backtest failed: `{type(e).__name__}: {e}`. "
                     f"Please rephrase the strategy or check the instrument/timeframe.")]
    _set_context(conv, backtest_result=bt)

    trades_all = bt.get("trades") or []
    n_all = len(trades_all)
    preview_n = 500
    display_trades = trades_all[-preview_n:] if n_all > preview_n else trades_all

    try:
        summary = llm_svc.summarize_results(
            strategy_name=_strategy_display_name(parsed),
            instrument=parsed["instrument"],
            timeframe=parsed["timeframe"],
            metrics=bt["metrics"],
        )
    except Exception as e:
        logger.exception("summarize_results failed")
        m = bt["metrics"]
        summary = (
            f"Backtested **{_strategy_display_name(parsed)}** on "
            f"{parsed['instrument']} {parsed['timeframe']} — {m.get('total_trades', 0)} trades, "
            f"{m.get('total_return_pct', 0):+.2f}% return, Sharpe {m.get('sharpe_ratio', 0):.2f}, "
            f"max DD {m.get('max_drawdown_pct', 0):.2f}%."
        )

    meta = {
        "kind": "backtest_result",
        "metrics": bt["metrics"],
        "equity_curve": bt["equity_curve"],
        "drawdown_curve": bt["drawdown_curve"],
        "trades": display_trades,
        "trades_truncated": n_all > preview_n,
        "full_trade_count": n_all,
        "params": bt["params"],
        "instrument": bt["instrument"],
        "timeframe": bt["timeframe"],
        "bars_used": bt.get("bars_used"),
        "from": bt.get("from"),
        "to": bt.get("to"),
        "date_range": bt.get("date_range"),
        "session_stats": bt.get("session_stats", {}),
        "rule_based_insights": bt.get("rule_based_insights"),
        "chart": bt.get("chart"),
        "explain": bt.get("explain", {}),
        "actions": _action_buttons_for_backtest(parsed),
    }
    conv.state = S_HAS_BACKTEST
    return [
        _msg(conv, "assistant", summary, "backtest_result", meta),
    ]


def _apply_edits_and_rerun(conv: Conversation, payload: Dict[str, Any]) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy") or {}
    new_params = payload.get("parameters") or {}
    parsed.setdefault("parameters", {}).update(new_params)
    new_inst = payload.get("instrument")
    if new_inst:
        parsed["instrument"] = new_inst
    new_tf = payload.get("timeframe")
    if new_tf:
        parsed["timeframe"] = new_tf
    _set_context(conv, parsed_strategy=parsed)
    conv.state = S_AWAITING_CONFIRM

    msgs = [_msg(conv, "assistant",
                 f"Updated parameters to `{new_params}`. Running the backtest now…",
                 "text")]
    msgs.extend(_run_backtest_step(conv))
    return msgs


def _run_finder_preview_step(conv: Conversation) -> List[Message]:
    """First step when user clicks Run Strategy Finder — Claude proposes the
    parameters and value ranges to test, the user can edit them, then they
    click Run Optimization to actually kick off the grid search."""
    from .executor import _strategy_class_from_parsed

    parsed = (conv.context or {}).get("parsed_strategy")
    bt = (conv.context or {}).get("backtest_result") or {}
    if not parsed:
        return [_msg(conv, "assistant",
                     "I don't have a parsed strategy in this conversation yet. "
                     "Describe one in the composer first, then I'll be able to optimize it.")]

    try:
        StratCls = _strategy_class_from_parsed(parsed)
    except Exception:
        return [_msg(conv, "assistant",
                     "I couldn't load this strategy's parameter shape. Run the backtest again first, then try Strategy Finder.")]

    template = parsed.get("template") or "custom_generated"
    template_defaults = {k: list(v) for k, v in (getattr(StratCls, "param_ranges", None) or {}).items()}
    accepted_params = dict(getattr(StratCls, "default_params", None) or {})

    proposal = llm_svc.propose_param_ranges(
        parsed_strategy=parsed,
        metrics=bt.get("metrics") or {},
        template_default_ranges=template_defaults,
        accepted_params=accepted_params,
    )
    ranges = proposal.get("ranges") or {}
    rationales = proposal.get("rationales") or {}
    focus = proposal.get("focus") or ""
    source = proposal.get("_source") or "template_defaults"

    if not ranges:
        return [_msg(conv, "assistant",
                     f"I couldn't find any tunable parameters for this strategy.")]

    fixed = {k: v for k, v in (parsed.get("parameters") or {}).items() if k not in ranges}
    n_combos = 1
    for v in ranges.values():
        n_combos *= max(1, len(v))

    body = (
        f"I'll grid-search **{n_combos}** parameter combinations to find a stronger version "
        f"of your strategy. Review the ranges below — you can edit any of them, then click "
        f"**Run Optimization** to start."
    )
    meta = {
        "kind": "sf_preview",
        "template": template,
        "instrument": parsed.get("instrument"),
        "timeframe": parsed.get("timeframe"),
        "param_ranges": ranges,
        "rationales": rationales,
        "focus": focus,
        "ai_source": source,
        "fixed_params": fixed,
        "n_combos": n_combos,
        "objective": "sharpe_ratio",
        "actions": [
            {"id": "confirm_run_finder", "label": "Run Optimization", "icon": "play"},
        ],
    }
    return [_msg(conv, "assistant", body, "sf_preview", meta)]


def _run_finder_step(conv: Conversation, payload: Optional[Dict[str, Any]] = None) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy")
    if not parsed:
        return [_msg(conv, "assistant",
                     "I don't have a parsed strategy in this conversation yet. "
                     "Describe one in the composer first, then I'll be able to optimize it.")]
    payload = payload or {}
    user_ranges = payload.get("ranges")
    user_objective = payload.get("objective")

    try:
        sf = execute_strategy_finder(
            parsed,
            objective=user_objective or "sharpe_ratio",
            param_ranges_override=user_ranges,
        )
    except Exception as e:
        logger.exception("strategy finder failed")
        return [_msg(conv, "assistant",
                     f"⚠️ Strategy Finder hit an error: `{type(e).__name__}: {e}`. "
                     f"Try re-running the base backtest first, then click Run Strategy Finder again.")]
    _set_context(conv, sf_result=sf)

    bt_ctx = (conv.context or {}).get("backtest_result") or {}
    original_metrics = dict(bt_ctx.get("metrics") or {})
    best_metrics = dict(sf["best_metrics"] or {})

    # Did the search actually find something better than the user's original
    # parameters on the chosen objective? Compare on the SF objective with a
    # tiny epsilon so floating-point noise doesn't claim a fake improvement.
    objective = sf["objective"]
    obj_keys = {
        "sharpe_ratio":  "sharpe_ratio",
        "total_return":  "total_return_pct",
        "profit_factor": "profit_factor",
        "expectancy":    "expectancy",
        "cagr":          "cagr_pct",
        "win_rate":      "win_rate_pct",
    }
    if objective == "calmar":
        def _score(m: Dict[str, Any]) -> float:
            ret = float(m.get("total_return_pct") or 0.0)
            dd = abs(float(m.get("max_drawdown_pct") or 0.0))
            return ret / dd if dd > 1e-9 else 0.0
    else:
        key = obj_keys.get(objective, "sharpe_ratio")
        def _score(m: Dict[str, Any]) -> float:
            return float(m.get(key) or 0.0)
    best_score = _score(best_metrics)
    orig_score = _score(original_metrics)
    best_beats_original = best_score > orig_score + 1e-6

    if best_beats_original:
        body = f"Tested **{sf['n_combos']}** parameter combinations — here's the best."
    else:
        body = (
            f"Tested **{sf['n_combos']}** combinations — none beat the original "
            f"on {objective.replace('_', ' ')}. Sticking with your current parameters."
        )

    meta = {
        "kind": "sf_result",
        "objective": objective,
        "ranked": sf["ranked"],
        "param_ranges": sf.get("param_ranges", {}),
        "fixed_params": sf.get("fixed_params", {}),
        "best_params": sf["best_params"],
        "best_metrics": best_metrics,
        "best_equity_curve": sf["best_equity_curve"],
        "n_combos": sf["n_combos"],
        "bars_used": sf.get("bars_used"),
        "from": sf.get("from"),
        "to": sf.get("to"),
        "walk_forward": sf.get("walk_forward"),
        # For before/after comparison in the UI:
        "original_params": dict(parsed.get("parameters") or {}),
        "original_metrics": original_metrics,
        "best_beats_original": best_beats_original,
        "actions": _action_buttons_for_optimized(parsed, best_beats_original=best_beats_original),
    }
    conv.state = S_HAS_OPTIMIZED
    return [_msg(conv, "assistant", body, "sf_result", meta)]


def _apply_best_params_step(conv: Conversation) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy") or {}
    sf = (conv.context or {}).get("sf_result") or {}
    if not sf.get("best_params"):
        return [_msg(conv, "assistant", "No Strategy Finder result yet.")]
    parsed.setdefault("parameters", {}).update(sf["best_params"])
    _set_context(conv, parsed_strategy=parsed)
    msgs = [_msg(conv, "assistant",
                 f"Applied best params `{sf['best_params']}` and re-running the backtest…",
                 "text")]
    msgs.extend(_run_backtest_step(conv))
    return msgs


def _run_filter_step(conv: Conversation) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy")
    bt = (conv.context or {}).get("backtest_result")
    if not parsed or not bt:
        return [_msg(conv, "assistant", "I need a backtest result before I can apply the AI filter.")]
    if not bt.get("trades"):
        return [_msg(conv, "assistant",
                     "The current backtest produced **zero trades**, so there's nothing for the "
                     "AI filter to score. Try a wider date range or different parameters first.")]

    try:
        fr = execute_ai_filter(parsed, bt)
    except Exception as e:
        logger.exception("ai filter failed")
        return [_msg(conv, "assistant",
                     f"⚠️ AI Filter hit an error: `{type(e).__name__}: {e}`. "
                     f"This usually means the cached backtest result is from an older session. "
                     f"Click **Run Backtest** again to refresh, then re-apply the AI filter.")]
    _set_context(conv, ai_filter_result=fr)

    before = fr["before_metrics"]
    after = fr["after_metrics"]
    mm = fr.get("model_meta", {})
    body = "Here are the results after applying the AI Filter."
    meta = {
        "kind": "ai_filter_result",
        "mode": fr["mode"],
        "threshold": fr["threshold"],
        "requested_threshold": fr.get("requested_threshold"),
        "auto_picked_threshold": fr.get("auto_picked_threshold", False),
        "scores": fr["scores"],
        "feature_columns": fr["feature_columns"],
        "feature_importances": fr["feature_importances"],
        "top_feature_importances": fr.get("top_feature_importances", {}),
        "feature_categories": fr.get("feature_categories", {}),
        "per_trade": fr["per_trade"],
        "kept_indices": fr["kept_indices"],
        "dropped_indices": fr["dropped_indices"],
        "before_metrics": before,
        "after_metrics": after,
        "after_equity_curve": fr["after_equity_curve"],
        "threshold_sweep": fr["threshold_sweep"],
        "total_trades": fr["total_trades"],
        "model_meta": mm,
        "actions": _action_buttons_for_filtered(),
    }
    conv.state = S_HAS_FILTERED
    return [_msg(conv, "assistant", body, "ai_filter_result", meta)]


def _run_improvements_step(conv: Conversation) -> List[Message]:
    ctx = conv.context or {}
    parsed = ctx.get("parsed_strategy")
    bt = ctx.get("backtest_result")
    sf = ctx.get("sf_result")
    fr = ctx.get("ai_filter_result")
    if not parsed or not bt:
        return [_msg(conv, "assistant", "Run a backtest first so I can review it.")]

    try:
        sugg = llm_svc.suggest_improvements(
            parsed,
            bt["metrics"],
            sf_result=sf,
            ai_filter_result=fr,
        )
    except Exception as e:
        logger.exception("suggest_improvements failed")
        return [_msg(conv, "assistant",
                     f"⚠️ Couldn't generate improvement suggestions right now: "
                     f"`{type(e).__name__}: {e}`. Try clicking the button again.")]
    body = "**Pros & cons of your current strategy + improvement plan:**"
    sf_done = bool(sf)
    ai_filter_done = bool(fr)
    imp_actions = []
    if not sf_done:
        imp_actions.append({"id": "run_finder", "label": "Run Strategy Finder", "icon": "search"})
    if not ai_filter_done:
        imp_actions.append({"id": "run_filter", "label": "Apply AI Filter", "icon": "sparkles"})
    meta = {
        "kind": "improvements",
        **sugg,
        "actions": imp_actions,
        "sf_done": sf_done,
        "ai_filter_done": ai_filter_done,
    }
    return [_msg(conv, "assistant", body, "improvements", meta)]


def _run_save_step(db: Session, conv: Conversation) -> List[Message]:
    parsed = (conv.context or {}).get("parsed_strategy")
    bt = (conv.context or {}).get("backtest_result")
    sf = (conv.context or {}).get("sf_result")
    fr = (conv.context or {}).get("ai_filter_result")
    if not parsed:
        return [_msg(conv, "assistant", "Nothing to save yet.")]

    status = "draft"
    if fr:
        status = "filtered"
    elif sf:
        status = "optimized"
    elif bt:
        status = "backtested"

    strat = Strategy(
        conversation_id=conv.id,
        name=conv.title,
        description=parsed.get("summary", ""),
        template=parsed["template"],
        parsed_logic=parsed,
        parameters=parsed.get("parameters", {}),
        instrument=parsed.get("instrument"),
        timeframe=parsed.get("timeframe"),
        backtest_result=bt or {},
        sf_result=sf or {},
        ai_filter_result=fr or {},
        status=status,
    )
    db.add(strat)
    db.flush()
    return [_msg(
        conv, "assistant",
        f"Saved as **{conv.title}** (status: {status}). You can find it in the sidebar under saved strategies.",
        "saved",
        {"strategy_id": strat.id, "status": status},
    )]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _strategy_display_name(parsed: Dict[str, Any]) -> str:
    label = parsed.get("strategy_label")
    if label and str(label).strip():
        return str(label).strip()
    # Never expose internal template identifiers ("bollinger_breakout",
    # "ema_crossover", "custom_my_strategy"). If we have no human label, fall
    # back to a generic name so the UI doesn't leak engine internals.
    return "Strategy"


def _make_title(parsed: Dict[str, Any]) -> str:
    name = _strategy_display_name(parsed)
    inst = parsed.get("instrument", "")
    tf = parsed.get("timeframe", "")
    return f"{name} · {inst} {tf}".strip()


def greet(conv: Conversation) -> Message:
    return _msg(
        conv,
        "assistant",
        (
            "Hi! I'm **QuantFlow**. Tell me a trading strategy in plain English and "
            "I'll parse it, backtest it, and help you improve it.\n\n"
            "For example:\n"
            "- *\"Heikin Ashi EMA 9 / 21 / 55 cross on XAUUSD 5m\"*\n"
            "- *\"RSI mean-reversion 14, buy below 30, sell above 70 on XAUUSD\"*\n"
            "- *\"Bollinger band 20 / 2 breakout strategy\"*\n\n"
            "Once I show the backtest, you'll get one-click buttons for **Strategy Finder** "
            "(parameter optimization) and the **AI Filter** (ML-based trade quality scoring)."
        ),
        "text",
    )
