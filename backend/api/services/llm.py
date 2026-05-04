"""LLM wrapper.

Two backends:
  - Claude API (when ANTHROPIC_API_KEY is set, default model claude-sonnet)
  - Mock heuristic fallback (no network) — keyword-based parser + canned
    summaries. Lets the whole chatbot work end-to-end offline for development.
"""
from __future__ import annotations
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import ANTHROPIC_API_KEY, ANTHROPIC_MODEL, llm_mode
from ...core.strategy import list_strategy_templates
from ...core.indicators import list_indicators
from ...data.instruments import list_instruments

_PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
_jinja_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    autoescape=select_autoescape(default=False),
    keep_trailing_newline=True,
)


def render_prompt(template_name: str, **ctx) -> str:
    return _jinja_env.get_template(template_name).render(**ctx)


# --------------------------------------------------------------------------- #
# Claude client
# --------------------------------------------------------------------------- #


def _claude_complete(prompt: str, system: Optional[str] = None,
                     temperature: float = 0.2, max_tokens: int = 2048) -> str:
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise RuntimeError("anthropic SDK not installed; run `pip install anthropic` or set QUANTFLOW_LLM_MODE=mock")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system or "You are QuantFlow's trading-strategy AI assistant.",
        messages=[{"role": "user", "content": prompt}],
    )
    parts = [b.text for b in msg.content if getattr(b, "type", "") == "text"]
    return "\n".join(parts).strip()


# --------------------------------------------------------------------------- #
# Mock parser (offline / dev mode)
# --------------------------------------------------------------------------- #


_DATE_RANGE_PATTERNS = [
    (re.compile(r"past\s+(\d+)\s+(year|years|yr|yrs)"),  "year"),
    (re.compile(r"past\s+(\d+)\s+(month|months|mo|mos)"), "month"),
    (re.compile(r"past\s+(\d+)\s+(week|weeks|wk|wks)"),   "week"),
    (re.compile(r"past\s+(\d+)\s+(day|days)"),            "day"),
    (re.compile(r"last\s+(\d+)\s+(year|years|yr|yrs)"),   "year"),
    (re.compile(r"last\s+(\d+)\s+(month|months|mo|mos)"), "month"),
    (re.compile(r"last\s+(\d+)\s+(week|weeks|wk|wks)"),   "week"),
    (re.compile(r"last\s+(\d+)\s+(day|days)"),            "day"),
]


def _extract_date_range(text: str) -> Dict[str, Any]:
    """Detect 'past N months/weeks/years' style phrases."""
    for rx, unit in _DATE_RANGE_PATTERNS:
        m = rx.search(text)
        if m:
            n = int(m.group(1))
            return {"type": "relative", "value": n, "unit": unit}
    return {"type": "all", "value": None, "unit": None}


def _mock_parse_strategy(user_message: str) -> Dict[str, Any]:
    """Keyword-based strategy parser. Maps the user request to a template."""
    text = user_message.lower()
    templates = {t["name"]: t for t in list_strategy_templates()}
    instruments = list_instruments()

    # ---- pick template
    if "heikin" in text or "ha " in text or " ha " in text:
        template = "heikin_ashi_ema_cross"
    elif "macd" in text:
        template = "macd_trend"
    elif "bollinger" in text or "bb" in text:
        template = "bollinger_breakout"
    elif "rsi" in text and ("oversold" in text or "overbought" in text or "mean revers" in text or "reversion" in text):
        template = "rsi_mean_reversion"
    elif "ema" in text or "moving average" in text or "crossover" in text:
        template = "ema_crossover"
    else:
        template = "ema_crossover"

    tpl = templates.get(template, templates["ema_crossover"])
    params = dict(tpl["default_params"])

    # ---- date range (past N months, last N weeks, etc.)
    date_range = _extract_date_range(text)

    # ---- extract numeric overrides like "ema 9 21 55", "rsi 14"
    # Strip out the date-range numbers first so they don't get mixed in.
    text_for_nums = text
    for rx, _ in _DATE_RANGE_PATTERNS:
        text_for_nums = rx.sub(" ", text_for_nums)
    nums = [int(n) for n in re.findall(r"\b\d+\b", text_for_nums)]
    if template in ("heikin_ashi_ema_cross", "ema_crossover"):
        ema_keys = ["ema_fast", "ema_slow"] + (["ema_trend"] if template == "heikin_ashi_ema_cross" else [])
        for i, k in enumerate(ema_keys):
            if i < len(nums):
                params[k] = nums[i]
    elif template == "rsi_mean_reversion":
        if nums:
            params["rsi_period"] = nums[0]
        for n in nums:
            if 60 <= n <= 90:
                params["rsi_upper"] = n
            elif 10 <= n <= 40:
                params["rsi_lower"] = n
    elif template == "bollinger_breakout":
        if nums:
            params["bb_period"] = nums[0]
        for n in nums:
            if n in (1, 2, 3):
                params["bb_std"] = float(n)
    elif template == "macd_trend":
        if len(nums) >= 3:
            params["fast"], params["slow"], params["signal"] = nums[0], nums[1], nums[2]

    # ---- pick instrument
    instrument = "XAUUSD"
    for inst in instruments:
        if inst["symbol"].lower() in text or inst["name"].lower() in text:
            instrument = inst["symbol"]
            break
    if "gold" in text or "xau" in text:
        instrument = "XAUUSD"

    chart: Optional[Dict[str, Any]] = None
    if "renko" in text:
        chart = {"type": "renko", "mode": "wicks"}
        m_brick = re.search(r"brick(?:\s*size)?[\s=:]+([\d.]+)", text)
        if m_brick:
            try:
                chart["brick_size"] = float(m_brick.group(1))
            except ValueError:
                pass
        if "nongap" in text or "no-gap" in text or "no gap" in text:
            chart["mode"] = "nongap"
        elif re.search(r"\bnormal\b", text) and "renko" in text:
            chart["mode"] = "normal"

    # ---- pick timeframe
    timeframe = "5m"
    if re.search(r"\b15\s*min", text) or "15m" in text:
        timeframe = "15m"
    elif re.search(r"\b5\s*min", text) or "5m" in text:
        timeframe = "5m"
    available_tfs = next((i["timeframes"] for i in instruments if i["symbol"] == instrument), ["5m"])
    if timeframe not in available_tfs:
        timeframe = available_tfs[0]

    # ---- POINT-based TP/SL detection: "tp 5 points sl 3 points", "tp = 5 sl = 3 points"
    tp_pts = sl_pts = 0.0
    m_tp = re.search(r"tp[\s=:]*([\d.]+)\s*(?:point|pt|pip)s?", text)
    m_sl = re.search(r"sl[\s=:]*([\d.]+)\s*(?:point|pt|pip)s?", text)
    if not m_tp:
        m_tp = re.search(r"take[\s\-]?profit[\s=:]*(?:of\s+)?([\d.]+)\s*(?:point|pt|pip)s?", text)
    if not m_sl:
        m_sl = re.search(r"stop[\s\-]?loss[\s=:]*(?:of\s+)?([\d.]+)\s*(?:point|pt|pip)s?", text)
    if m_tp:
        tp_pts = float(m_tp.group(1))
        if "tp_points" in params or template == "ema_crossover":
            params["tp_points"] = tp_pts
    if m_sl:
        sl_pts = float(m_sl.group(1))
        if "sl_points" in params or template == "ema_crossover":
            params["sl_points"] = sl_pts

    # ---- ATR-based SL/TP detection (only if no point-based was found)
    use_sl_tp = (tp_pts == 0 and sl_pts == 0) and (
        ("stop" in text and "loss" in text) or "sl/tp" in text or "atr stop" in text
    )
    if use_sl_tp and "use_sl_tp" in params:
        params["use_sl_tp"] = True

    range_clause = ""
    if date_range["type"] == "relative":
        range_clause = f" over the past {date_range['value']} {date_range['unit']}{'s' if date_range['value'] != 1 and not date_range['unit'].endswith('s') else ''}"

    summary = (
        f"You want a {template.replace('_', ' ')} on {instrument} {timeframe}{range_clause}. "
        f"I'll use parameters {params}."
    )
    if chart:
        bs = chart.get("brick_size")
        bs_txt = f"brick size {bs}" if bs else "automatic brick size (median heuristic)"
        summary += f" **Renko chart** — mode `{chart['mode']}`, {bs_txt}."

    sl_block = (
        {"type": "fixed", "value": sl_pts} if sl_pts > 0
        else ({"type": "atr", "value": params.get("atr_sl_mult")} if use_sl_tp else {"type": "none", "value": None})
    )
    tp_block = (
        {"type": "fixed", "value": tp_pts} if tp_pts > 0
        else ({"type": "atr", "value": params.get("atr_tp_mult")} if use_sl_tp else {"type": "none", "value": None})
    )
    return {
        "template": template,
        "instrument": instrument,
        "timeframe": timeframe,
        "date_range": date_range,
        "parameters": params,
        "entry_rules": _mock_entry_rules(template, params),
        "exit_rules": _mock_exit_rules(template),
        "stop_loss": sl_block,
        "take_profit": tp_block,
        "indicators_used": _mock_indicators_used(template, params),
        "position_sizing": {"type": "fixed_units", "value": 1},
        "needs_clarification": False,
        "questions": [],
        "summary": summary,
        "chart": chart,
    }


def _mock_entry_rules(template: str, p: Dict[str, Any]) -> List[str]:
    if template == "heikin_ashi_ema_cross":
        return [
            f"LONG: HA-EMA({p['ema_fast']}) crosses ABOVE HA-EMA({p['ema_slow']}) AND price > EMA({p['ema_trend']})",
            f"SHORT: HA-EMA({p['ema_fast']}) crosses BELOW HA-EMA({p['ema_slow']}) AND price < EMA({p['ema_trend']})",
        ]
    if template == "ema_crossover":
        rules = [
            f"LONG: EMA({p['ema_fast']}) crosses ABOVE EMA({p['ema_slow']})",
            f"SHORT: EMA({p['ema_fast']}) crosses BELOW EMA({p['ema_slow']})",
        ]
        if p.get("use_adx_filter"):
            rules.append(f"FILTER: ADX({p['adx_period']}) >= {p['adx_threshold']}")
        return rules
    if template == "rsi_mean_reversion":
        return [
            f"LONG: RSI({p['rsi_period']}) crosses ABOVE {p['rsi_lower']}",
            f"SHORT: RSI({p['rsi_period']}) crosses BELOW {p['rsi_upper']}",
        ]
    if template == "bollinger_breakout":
        return [
            f"LONG: close breaks ABOVE upper Bollinger band ({p['bb_period']}, {p['bb_std']}σ)",
            f"SHORT: close breaks BELOW lower Bollinger band",
        ]
    if template == "macd_trend":
        return [
            f"LONG: MACD histogram ({p['fast']},{p['slow']},{p['signal']}) crosses ABOVE 0",
            f"SHORT: MACD histogram crosses BELOW 0",
        ]
    return ["entry conditions"]


def _mock_exit_rules(template: str) -> List[str]:
    if template in ("heikin_ashi_ema_cross", "ema_crossover", "macd_trend"):
        return ["EXIT: opposite entry signal"]
    if template == "rsi_mean_reversion":
        return ["EXIT: RSI returns through the middle band (50)"]
    if template == "bollinger_breakout":
        return ["EXIT: close back through Bollinger middle"]
    return ["EXIT: opposite signal"]


def _mock_indicators_used(template: str, p: Dict[str, Any]) -> List[str]:
    if template == "heikin_ashi_ema_cross":
        return [f"heikin_ashi", f"ema({p['ema_fast']})", f"ema({p['ema_slow']})", f"ema({p['ema_trend']})"]
    if template == "ema_crossover":
        ind = [f"ema({p['ema_fast']})", f"ema({p['ema_slow']})"]
        if p.get("use_adx_filter"):
            ind.append(f"adx({p['adx_period']})")
        return ind
    if template == "rsi_mean_reversion":
        return [f"rsi({p['rsi_period']})"]
    if template == "bollinger_breakout":
        return [f"bollinger_bands({p['bb_period']},{p['bb_std']})"]
    if template == "macd_trend":
        return [f"macd({p['fast']},{p['slow']},{p['signal']})"]
    return []


def _mock_summarize(strategy_name: str, instrument: str, timeframe: str, metrics: Dict[str, Any]) -> str:
    ret = metrics.get("total_return_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    dd = metrics.get("max_drawdown_pct", 0)
    n = metrics.get("n_trades", 0)
    pf = metrics.get("profit_factor", 0)
    wr = metrics.get("win_rate_pct", 0)
    return (
        f"**{strategy_name}** on {instrument} {timeframe}: "
        f"{ret:+.2f}% return over {n} trades, Sharpe {sharpe:.2f}, max DD {dd:.2f}%, "
        f"profit factor {pf:.2f}, win rate {wr:.1f}%."
    )


def _mock_improve(parsed_strategy: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    template = parsed_strategy.get("template", "")
    params = parsed_strategy.get("parameters", {})

    pf = metrics.get("profit_factor", 0)
    wr = metrics.get("win_rate_pct", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    dd = abs(metrics.get("max_drawdown_pct", 0))
    n = metrics.get("n_trades", 0)
    ret = metrics.get("total_return_pct", 0)

    pros: List[str] = []
    cons: List[str] = []

    if ret > 0:
        pros.append(f"Positive total return of {ret:.2f}%.")
    else:
        cons.append(f"Negative or flat return of {ret:.2f}%.")
    if sharpe >= 1:
        pros.append(f"Decent risk-adjusted performance (Sharpe {sharpe:.2f}).")
    else:
        cons.append(f"Low Sharpe of {sharpe:.2f} — risk-adjusted return is weak.")
    if pf >= 1.3:
        pros.append(f"Healthy profit factor of {pf:.2f} (wins outweigh losses).")
    else:
        cons.append(f"Profit factor {pf:.2f} is below 1.3 — losses eat into wins.")
    if wr >= 45:
        pros.append(f"Reasonable win rate of {wr:.1f}%.")
    elif wr < 35:
        cons.append(f"Win rate {wr:.1f}% is low — many false signals.")
    if dd > 0 and ret > 0 and (ret / dd) < 1.0:
        cons.append(f"Drawdown ({dd:.1f}%) exceeds total return ({ret:.1f}%).")
    if n < 30:
        cons.append(f"Only {n} trades — sample size too small to be statistically reliable.")

    basic_filters = []
    if template in ("ema_crossover", "macd_trend") and not params.get("use_adx_filter"):
        basic_filters.append({
            "name": "Add ADX > 20 trend filter",
            "rationale": "Filters out chop and low-trend regimes that hurt crossover strategies.",
            "param": "use_adx_filter",
            "value": True,
        })
    if not params.get("use_sl_tp") and template in ("heikin_ashi_ema_cross", "ema_crossover"):
        basic_filters.append({
            "name": "Enable ATR-based stop-loss / take-profit",
            "rationale": "Caps worst-trade impact and locks in gains in volatile regimes.",
            "param": "use_sl_tp",
            "value": True,
        })
    if template == "rsi_mean_reversion" and not params.get("use_trend_filter"):
        basic_filters.append({
            "name": "Add 200-EMA trend filter",
            "rationale": "Only take longs above EMA(200) and shorts below — avoids fading strong trends.",
            "param": "use_trend_filter",
            "value": True,
        })

    ranges = {}
    if template == "heikin_ashi_ema_cross":
        ranges = {"ema_fast": [5, 7, 9, 12], "ema_slow": [15, 21, 26, 34], "ema_trend": [50, 55, 100, 200]}
    elif template == "ema_crossover":
        ranges = {"ema_fast": [5, 9, 12, 20], "ema_slow": [21, 26, 50, 100]}
    elif template == "rsi_mean_reversion":
        ranges = {"rsi_period": [7, 14, 21], "rsi_lower": [20, 25, 30], "rsi_upper": [70, 75, 80]}
    elif template == "bollinger_breakout":
        ranges = {"bb_period": [10, 20, 30], "bb_std": [1.5, 2.0, 2.5]}
    elif template == "macd_trend":
        ranges = {"fast": [8, 12], "slow": [21, 26], "signal": [7, 9]}

    next_steps = []
    if basic_filters:
        next_steps.append(f"Apply: {basic_filters[0]['name']}.")
    if ranges:
        next_steps.append("Run Strategy Finder over the suggested parameter ranges.")
    next_steps.append("Apply the AI Filter on the optimized version to drop low-quality trades.")

    # Cap pros + cons at 5 combined, picking the strongest signals first.
    combined_budget = 5
    pros = pros[: max(1, combined_budget // 2)]
    cons = cons[: combined_budget - len(pros)]

    return {
        "pros": pros,
        "cons": cons,
        "basic_filter_suggestions": basic_filters,
        "ai_filter_suggestion": {
            "should_run": pf < 2.0,
            "expected_uplift": (
                "Typically lifts profit factor by 0.2-0.5 and reduces drawdown by removing "
                "low-conviction entries."
            ),
            "rationale": "AI filter scores each entry on context features (ADX, RSI, BB position, trend alignment) "
                         "and drops those below threshold. Most useful when the base strategy has many false signals.",
        },
        "param_tuning_suggestion": {
            "should_run": bool(ranges),
            "ranges_to_explore": ranges,
            "objective": "sharpe_ratio",
        },
        "ranked_next_steps": next_steps,
    }


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def parse_strategy(
    user_message: str,
    conversation_context: Optional[str] = None,
    prior_spec: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Parse a natural-language strategy request into a structured spec.

    When QUANTFLOW_LLM_MODE=claude (or auto with a key set) we hit Claude.
    On Claude failure we still fall back to the heuristic parser to keep the
    chatbot working, but we attach `_parsed_by` and `_llm_error` telemetry to
    the spec so the UI / orchestrator can be honest about what happened.

    ``conversation_context`` should be a plain-text transcript of recent turns
    (user+assistant) so refinements like *"make the slow EMA 34"* are interpreted
    relative to the active strategy draft.

    ``prior_spec`` is the **structured** previous parse if the user is iterating
    on an existing draft. Passing this lets the LLM produce a clean delta-merge
    (change a parameter, add a filter) without losing fields it never re-states.
    """
    ctx = conversation_context or ""
    prior_for_prompt = _slim_prior_spec_for_prompt(prior_spec) if prior_spec else None
    if llm_mode() == "claude":
        try:
            prompt = render_prompt(
                "strategy_parser.jinja2",
                user_message=user_message,
                conversation_context=ctx,
                prior_spec=prior_for_prompt,
                templates=list_strategy_templates(),
                instruments=list_instruments(),
                indicators=[i["name"] for i in list_indicators()],
            )
            raw = _claude_complete(prompt, temperature=0.0, max_tokens=8192)
            spec = _extract_json(raw)
            if spec is not None:
                spec = _validate_spec(spec, user_message)
                spec["_parsed_by"] = "claude"
                spec["_llm_raw_excerpt"] = raw[:300]
                return spec
            # JSON parse failed → log loudly, return mock spec marked as such
            logger.warning("Claude returned non-JSON. Raw output: %s", raw[:500])
            spec = _validate_spec(_mock_parse_strategy(user_message), user_message)
            spec["_parsed_by"] = "fallback_mock"
            spec["_llm_error"] = "Claude returned a response that wasn't valid JSON."
            spec["_llm_raw_excerpt"] = raw[:300]
            return spec
        except Exception as e:
            logger.exception("Claude parse failed")
            spec = _validate_spec(_mock_parse_strategy(user_message), user_message)
            spec["_parsed_by"] = "fallback_mock"
            spec["_llm_error"] = f"{type(e).__name__}: {e}"
            return spec

    spec = _validate_spec(_mock_parse_strategy(user_message), user_message)
    spec["_parsed_by"] = "mock"
    return spec


def summarize_results(strategy_name: str, instrument: str, timeframe: str,
                      metrics: Dict[str, Any]) -> str:
    if llm_mode() == "claude":
        try:
            prompt = render_prompt(
                "results_summarizer.jinja2",
                strategy_name=strategy_name,
                instrument=instrument,
                timeframe=timeframe,
                metrics=metrics,
            )
            return _claude_complete(prompt, temperature=0.4, max_tokens=600)
        except Exception:
            pass
    return _mock_summarize(strategy_name, instrument, timeframe, metrics)


def suggest_improvements(parsed_strategy: Dict[str, Any],
                         metrics: Dict[str, Any],
                         sf_result: Optional[Dict[str, Any]] = None,
                         ai_filter_result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sf_summary = _summarize_sf_for_critique(sf_result) if sf_result else None
    fr_summary = _summarize_filter_for_critique(ai_filter_result) if ai_filter_result else None
    indicator_hints = _extract_indicator_hints(ai_filter_result) if ai_filter_result else []

    if llm_mode() == "claude":
        try:
            prompt = render_prompt(
                "improvement_suggester.jinja2",
                strategy_name=parsed_strategy.get("template", ""),
                template=parsed_strategy.get("template", ""),
                instrument=parsed_strategy.get("instrument", ""),
                timeframe=parsed_strategy.get("timeframe", ""),
                parameters=parsed_strategy.get("parameters", {}),
                metrics=metrics,
                sf_summary=sf_summary,
                ai_filter_summary=fr_summary,
                indicator_hints=indicator_hints,
                sf_done=bool(sf_result),
                ai_filter_done=bool(ai_filter_result),
            )
            raw = _claude_complete(prompt, temperature=0.2, max_tokens=1500)
            spec = _extract_json(raw)
            if spec:
                return spec
        except Exception:
            pass
    return _mock_improve(parsed_strategy, metrics)


_PRIOR_SPEC_KEYS = (
    "implementation_mode",
    "strategy_label",
    "template",
    "instrument",
    "timeframe",
    "date_range",
    "parameters",
    "entry_rules",
    "exit_rules",
    "extra_filters",
    "extra_filters_supported",
    "stop_loss",
    "take_profit",
    "indicators_used",
    "position_sizing",
    "chart",
    "summary",
)


def _slim_prior_spec_for_prompt(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Strip telemetry & generated source from a prior parse before feeding it
    back to the parser as refinement context. Keeps the spec surface area
    small so the LLM can re-emit a clean delta-merged JSON."""
    if not spec:
        return {}
    out = {k: spec[k] for k in _PRIOR_SPEC_KEYS if k in spec}
    # generated_python is large and the parser will re-emit it from scratch
    # if the user's edit affects the custom logic; otherwise registry path stays.
    if spec.get("implementation_mode") == "generated_class":
        out["had_generated_python"] = True
    return out


def propose_param_ranges(
    parsed_strategy: Dict[str, Any],
    metrics: Dict[str, Any],
    template_default_ranges: Optional[Dict[str, Any]] = None,
    accepted_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Have Claude pick the parameters and value ranges to grid-search, given the
    strategy and its current backtest result. Returns a dict with ``ranges``,
    ``rationales`` and ``focus`` (one-line summary). Falls back to the template's
    declared param_ranges if Claude is unavailable or returns invalid JSON.

    ``accepted_params`` is the strategy class's real ``default_params`` dict — the
    AUTHORITATIVE list of params the strategy actually reads. Anything else is
    inert and would silently be dropped by the search engine, so we constrain
    Claude to propose only from this set.
    """
    fallback = {
        "ranges": {k: list(v) for k, v in (template_default_ranges or {}).items()},
        "rationales": {},
        "focus": "Sweeping the strategy's default parameter ranges.",
        "_source": "template_defaults",
    }
    if llm_mode() != "claude":
        return fallback

    # The strategy class's real param surface. If not provided, fall back to
    # whatever's in parsed.parameters (less safe — may include hallucinated keys).
    accepted = accepted_params if accepted_params is not None else (parsed_strategy.get("parameters") or {})

    try:
        prompt = render_prompt(
            "param_ranges_proposer.jinja2",
            template=parsed_strategy.get("template", ""),
            strategy_label=parsed_strategy.get("strategy_label") or parsed_strategy.get("template", ""),
            instrument=parsed_strategy.get("instrument", ""),
            timeframe=parsed_strategy.get("timeframe", ""),
            current_parameters=accepted,
            indicators_used=parsed_strategy.get("indicators_used", []) or [],
            entry_rules=parsed_strategy.get("entry_rules", []) or [],
            exit_rules=parsed_strategy.get("exit_rules", []) or [],
            metrics=metrics or {},
            template_default_ranges=template_default_ranges or {},
        )
        raw = _claude_complete(prompt, temperature=0.2, max_tokens=1500)
        spec = _extract_json(raw)
        if not spec or not isinstance(spec.get("ranges"), dict):
            logger.warning("propose_param_ranges: Claude returned no valid ranges; using template defaults.")
            return fallback

        ranges_in = spec.get("ranges") or {}
        cleaned: Dict[str, Any] = {}
        dropped: list[str] = []
        for k, v in ranges_in.items():
            if k not in accepted:
                dropped.append(k)
                continue
            if not isinstance(v, list) or len(v) == 0:
                continue
            cleaned[k] = v
        if dropped:
            logger.warning(
                "propose_param_ranges: dropped %s — not in strategy's default_params",
                dropped,
            )
        if not cleaned:
            logger.warning("propose_param_ranges: every Claude-suggested param was filtered out; using defaults.")
            return fallback

        return {
            "ranges": cleaned,
            "rationales": {
                k: spec["rationales"][k]
                for k in cleaned.keys()
                if isinstance(spec.get("rationales"), dict) and k in spec["rationales"]
            },
            "focus": str(spec.get("focus") or "")[:240],
            "_source": "claude",
        }
    except Exception as e:
        logger.exception("propose_param_ranges failed: %s", e)
        return fallback


def _summarize_sf_for_critique(sf: Dict[str, Any]) -> Dict[str, Any]:
    """Slim view of the Strategy Finder result for the improvements prompt."""
    if not sf:
        return {}
    best = sf.get("best_params") or {}
    metrics = sf.get("best_metrics") or sf.get("metrics") or {}
    n_combos = sf.get("n_combinations_tested") or sf.get("n_tested") or len(sf.get("results") or [])
    return {
        "best_params": best,
        "best_metrics": {
            k: metrics.get(k)
            for k in ("total_return_pct", "sharpe_ratio", "max_drawdown_pct",
                      "profit_factor", "win_rate_pct", "n_trades")
            if k in metrics
        },
        "combinations_tested": n_combos,
    }


def _summarize_filter_for_critique(fr: Dict[str, Any]) -> Dict[str, Any]:
    """Slim view of the AI Filter result for the improvements prompt — no model internals."""
    if not fr:
        return {}
    before = fr.get("before_metrics") or {}
    after = fr.get("after_metrics") or {}
    kept = len(fr.get("kept_indices") or [])
    total = fr.get("total_trades") or len(fr.get("scores") or [])
    keys = ("total_return_pct", "sharpe_ratio", "max_drawdown_pct",
            "profit_factor", "win_rate_pct", "n_trades", "total_points")
    return {
        "before": {k: before.get(k) for k in keys if k in before},
        "after": {k: after.get(k) for k in keys if k in after},
        "trades_kept": kept,
        "trades_total": total,
        "trades_dropped_pct": round((1 - kept / max(1, total)) * 100, 1),
    }


def _extract_indicator_hints(fr: Dict[str, Any], top_n: int = 8) -> List[str]:
    """Reduce model feature importances to short trader-language indicator labels.

    The improvements LLM uses these as ANONYMOUS observations (e.g. "ADX seems
    to discriminate winners well") — never as "the model selected this feature".
    The whole point: keep model internals hidden but still let the coach point
    the user at indicators that are worth filtering on.
    """
    if not fr:
        return []
    importances = fr.get("top_feature_importances") or fr.get("feature_importances") or {}
    if not isinstance(importances, dict) or not importances:
        return []
    try:
        ranked = sorted(importances.items(), key=lambda kv: float(kv[1] or 0), reverse=True)
    except Exception:
        return []

    seen: set[str] = set()
    out: List[str] = []
    for raw_name, _imp in ranked:
        label = _indicator_label_from_feature_name(str(raw_name))
        if not label or label in seen:
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= top_n:
            break
    return out


_INDICATOR_LABEL_MAP: List[Tuple[str, str]] = [
    ("adx", "ADX (trend strength)"),
    ("rsi", "RSI (momentum)"),
    ("macd", "MACD"),
    ("atr", "ATR (volatility)"),
    ("bb_", "Bollinger Bands"),
    ("bband", "Bollinger Bands"),
    ("boll", "Bollinger Bands"),
    ("ema", "EMA distance / slope"),
    ("sma", "SMA distance"),
    ("vwap", "VWAP distance"),
    ("obv", "OBV (volume flow)"),
    ("supertrend", "Supertrend"),
    ("keltner", "Keltner Channel"),
    ("stoch", "Stochastic"),
    ("roc", "Rate of Change"),
    ("hour", "time-of-day / session"),
    ("session", "time-of-day / session"),
    ("dow", "day-of-week"),
    ("weekday", "day-of-week"),
    ("volume", "volume"),
    ("liq", "liquidity sweep / SMC"),
    ("fvg", "fair-value gap (SMC)"),
    ("ob_", "order block (SMC)"),
    ("bos", "break-of-structure (SMC)"),
    ("choch", "change-of-character (SMC)"),
    ("swing", "swing structure"),
    ("range", "range / volatility"),
]


def _indicator_label_from_feature_name(name: str) -> Optional[str]:
    """Best-effort mapping of a raw feature column to a trader-language label.

    Returns ``None`` for noise / unmappable columns so the caller can skip them.
    """
    if not name:
        return None
    n = name.lower()
    for prefix, label in _INDICATOR_LABEL_MAP:
        if prefix in n:
            return label
    return None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    raw = raw.strip()
    # strip markdown fences if any
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?", "", raw).rstrip("`").strip()
    m = _JSON_RE.search(raw)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _validate_spec(spec: Dict[str, Any], user_message: str) -> Dict[str, Any]:
    """Ensure instrument/timeframe exist; load registry template OR generated class."""
    from ...core.strategy.dynamic_loader import load_strategy_class_from_source

    templates = {t["name"]: t for t in list_strategy_templates()}
    instruments = {i["symbol"]: i for i in list_instruments()}

    impl = spec.get("implementation_mode") or "registry_template"
    if impl not in ("registry_template", "generated_class"):
        impl = "registry_template"
    spec["implementation_mode"] = impl
    spec.setdefault("generated_python", "")
    spec.setdefault("strategy_label", "")

    if spec.get("instrument") not in instruments:
        spec["instrument"] = next(iter(instruments))
    inst = instruments[spec["instrument"]]
    if spec.get("timeframe") not in inst["timeframes"]:
        spec["timeframe"] = inst["timeframes"][0]

    spec.setdefault("entry_rules", [])
    spec.setdefault("exit_rules", [])
    spec.setdefault("extra_filters", [])
    spec.setdefault("indicators_used", [])
    spec.setdefault("needs_clarification", False)
    spec.setdefault("questions", [])
    spec.setdefault("summary", _mock_parse_strategy(user_message)["summary"])
    spec.setdefault("stop_loss", {"type": "none", "value": None})
    spec.setdefault("take_profit", {"type": "none", "value": None})
    spec.setdefault("position_sizing", {"type": "fixed_units", "value": 1})
    spec.setdefault("extra_filters_supported", True)
    if "date_range" not in spec:
        spec["date_range"] = _extract_date_range(user_message.lower())

    chart_in = spec.get("chart")
    if isinstance(chart_in, dict) and str(chart_in.get("type", "")).lower() == "renko":
        chart_in["type"] = "renko"
        chart_in["mode"] = str(chart_in.get("mode") or "wicks").strip() or "wicks"
        bs = chart_in.get("brick_size")
        if bs is None:
            chart_in.pop("brick_size", None)
        else:
            try:
                bf = float(bs)
                if bf > 0:
                    chart_in["brick_size"] = bf
                else:
                    chart_in.pop("brick_size", None)
            except (TypeError, ValueError):
                chart_in.pop("brick_size", None)
        spec["chart"] = chart_in
    else:
        spec["chart"] = None

    # Force generated_class — registry templates are no longer used as the
    # primary path. If Claude returned registry_template anyway, treat the
    # generated_python as missing and try to recover.
    spec["implementation_mode"] = "generated_class"
    spec["template"] = "custom_generated"

    src = (spec.get("generated_python") or "").strip()
    cls = None
    last_err: Optional[str] = None
    if src:
        try:
            cls = load_strategy_class_from_source(src)
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            logger.warning("generated_class failed initial validation: %s", e)
            cls = None

    if cls is None and llm_mode() == "claude":
        try:
            # Re-render the full parser prompt so Claude sees the no-imports
            # rule, the indicator helper whitelist, and the JSON schema. Append
            # the previous compile error as a hint at the top.
            base = render_prompt(
                "strategy_parser.jinja2",
                user_message=user_message,
                conversation_context="",
                prior_spec=None,
                templates=list_strategy_templates(),
                instruments=list_instruments(),
                indicators=[i["name"] for i in list_indicators()],
            )
            retry_prompt = (
                f"⚠️ PREVIOUS ATTEMPT FAILED. Compile error: {last_err or 'no generated_python provided'}.\n"
                "Common causes: `import` / `from x import y` (forbidden — use ONLY the "
                "injected helpers), missing `GeneratedStrategy` class, dunder access, or "
                "a syntax error. Re-emit the spec WITHOUT those mistakes.\n\n"
                + base
            )
            raw = _claude_complete(retry_prompt, temperature=0.0, max_tokens=8192)
            retry_spec = _extract_json(raw)
            retry_src = (retry_spec or {}).get("generated_python") or ""
            if retry_src.strip():
                cls = load_strategy_class_from_source(retry_src)
                spec["generated_python"] = retry_src
                src = retry_src
                last_err = None
                # Also pull the retry's parameters / rules / summary so the
                # confirmation card matches the code that actually compiled.
                for k in ("parameters", "entry_rules", "exit_rules", "indicators_used",
                          "summary", "strategy_label"):
                    if retry_spec and retry_spec.get(k):
                        spec[k] = retry_spec[k]
        except Exception as e:
            logger.warning("generated_class retry also failed: %s", e)
            last_err = f"{type(e).__name__}: {e}"
            cls = None

    if cls is not None:
        accepted = dict(cls.default_params)
        user_provided = spec.get("parameters") or {}
        merged = {k: user_provided.get(k, v) for k, v in accepted.items()}
        spec["parameters"] = merged
        if not spec.get("strategy_label"):
            nm = getattr(cls, "name", None) or "custom_strategy"
            spec["strategy_label"] = str(nm).replace("_", " ").strip().title()
        spec["_codegen_error"] = None
        return spec

    # Total failure — no template fallback. Surface a clear trader-language
    # error so the user can rephrase. Keep `parameters` empty so no phantom
    # ADX/ATR knobs leak into the UI.
    spec["parameters"] = {}
    spec["_codegen_error"] = last_err or "no_generated_python"
    spec["needs_clarification"] = True
    spec.setdefault("questions", []).append(
        "I couldn't translate that into runnable strategy logic. Could you rephrase "
        "with the indicator names and the exact entry / exit / stop rules?"
    )
    return spec


# Human-readable indicator names for error messages (lazy import avoids circulars)
INDICATOR_NAMES = [i["name"] for i in list_indicators()]
