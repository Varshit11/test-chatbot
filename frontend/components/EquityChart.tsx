"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  Legend,
  Line,
  ComposedChart,
} from "recharts";

interface Point {
  t: string;
  equity?: number;
  equity2?: number;
  dd?: number;
}

interface Props {
  data: Point[];
  initial: number;
  height?: number;
  compareLabel?: string;
}

export function EquityChart({ data, initial, height = 220, compareLabel }: Props) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-32 items-center justify-center text-xs text-ink-dim">
        No equity data
      </div>
    );
  }
  return (
    <div className="-mx-1" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#d97757" stopOpacity={0.45} />
              <stop offset="100%" stopColor="#d97757" stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="equityFill2" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#22c55e" stopOpacity={0.4} />
              <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#23232a" strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fill: "#6b7180", fontSize: 10 }} hide />
          <YAxis
            tick={{ fill: "#6b7180", fontSize: 10 }}
            domain={["dataMin", "dataMax"]}
            tickFormatter={(v) => Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}
            width={60}
          />
          <Tooltip
            contentStyle={{
              background: "#15151a",
              border: "1px solid #23232a",
              borderRadius: 6,
              fontSize: 12,
            }}
            labelStyle={{ color: "#9aa0aa" }}
            formatter={(v: any, n: any) => [Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 }), n]}
          />
          {compareLabel && <Legend wrapperStyle={{ fontSize: 11, color: "#9aa0aa" }} />}
          <Area
            type="monotone"
            dataKey="equity"
            stroke="#d97757"
            strokeWidth={2}
            fill="url(#equityFill)"
            name="Equity"
            isAnimationActive={false}
          />
          {compareLabel && (
            <Area
              type="monotone"
              dataKey="equity2"
              stroke="#22c55e"
              strokeWidth={2}
              fill="url(#equityFill2)"
              name={compareLabel}
              isAnimationActive={false}
            />
          )}
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DrawdownChart({ data, height = 110 }: { data: { t: string; dd: number }[]; height?: number }) {
  if (!data || data.length === 0) return null;
  const dataPct = data.map((p) => ({ t: p.t, dd: p.dd * 100 }));
  return (
    <div className="-mx-1" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={dataPct} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity={0.5} />
              <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="#23232a" strokeDasharray="3 3" />
          <XAxis dataKey="t" tick={{ fill: "#6b7180", fontSize: 10 }} hide />
          <YAxis
            tick={{ fill: "#6b7180", fontSize: 10 }}
            tickFormatter={(v) => `${Number(v).toFixed(1)}%`}
            width={50}
          />
          <Tooltip
            contentStyle={{ background: "#15151a", border: "1px solid #23232a", borderRadius: 6, fontSize: 12 }}
            formatter={(v: any) => [`${Number(v).toFixed(2)}%`, "Drawdown"]}
            labelStyle={{ color: "#9aa0aa" }}
          />
          <Area
            type="monotone"
            dataKey="dd"
            stroke="#ef4444"
            strokeWidth={1.6}
            fill="url(#ddFill)"
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
