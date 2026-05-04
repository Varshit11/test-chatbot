export type MsgType =
  | "text"
  | "strategy_confirmation"
  | "backtest_result"
  | "sf_result"
  | "ai_filter_result"
  | "improvements"
  | "saved";

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  msg_type: MsgType;
  metadata?: Record<string, any>;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string;
  status: string;
  state: string;
  created_at: string;
  updated_at: string;
  messages?: Message[];
  context?: Record<string, any>;
}

export interface SavedStrategy {
  id: string;
  name: string;
  description: string;
  template?: string;
  instrument?: string;
  timeframe?: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ParsedStrategy {
  template: string;
  instrument: string;
  timeframe: string;
  parameters: Record<string, any>;
  entry_rules: string[];
  exit_rules: string[];
  stop_loss: { type: string; value: number | null };
  take_profit: { type: string; value: number | null };
  indicators_used: string[];
  position_sizing: { type: string; value: number };
  needs_clarification: boolean;
  questions: string[];
  summary: string;
  /** Human-readable name from the LLM */
  strategy_label?: string;
  /** `generated_class` when codegen path is used */
  implementation_mode?: "registry_template" | "generated_class";
  /** Full Python class source when implementation_mode is generated */
  generated_python?: string;
  /** Optional chart transform e.g. Renko built from time bars */
  chart?: { type: string; mode?: string; brick_size?: number | null } | null;
}

export interface MetricsBundle {
  initial_capital: number;
  final_equity: number;
  total_return_pct: number;
  cagr_pct: number;
  max_drawdown_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  n_trades: number;
  long_trades: number;
  short_trades: number;
  win_rate_pct: number;
  avg_win: number;
  avg_loss: number;
  avg_trade: number;
  best_trade: number;
  worst_trade: number;
  profit_factor: number;
  expectancy: number;
  gross_profit: number;
  gross_loss: number;
  total_points: number;
  avg_points: number;
  avg_points_win: number;
  avg_points_loss: number;
  best_points: number;
  worst_points: number;
}

export interface StrategyExplain {
  name: string;
  description: string;
  params: Record<string, any>;
  entry_rules: string[];
  exit_rules: string[];
  indicators: string[];
  code_snippet: string;
  /** Present for codegen strategies: entire module/class source */
  full_strategy_source?: string;
  implementation_mode?: string;
}

export interface ActionButton {
  id: string;
  label: string;
  icon?: string;
}

export interface EquityPoint {
  t: string;
  equity: number;
}

export interface DDPoint {
  t: string;
  dd: number;
}

export interface Trade {
  side: string;
  entry_time: string;
  entry_price: number;
  exit_time?: string;
  exit_price?: number;
  pnl: number;
  pnl_pct: number;
  points?: number;
  bars_held: number;
  exit_reason: string;
}
