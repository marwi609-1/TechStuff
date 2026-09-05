import type { ChartContext } from "./mock-context";

export type GenerateResult = {
  agentNotes: string[];
  title: string;
  pine: string;
  mode: "strategy" | "indicator";
};

function numParam(
  inds: ChartContext["indicators"],
  name: string,
  key: string,
  fallback: number,
): number {
  const hit = inds.find((i) => i.name.toUpperCase() === name.toUpperCase());
  if (!hit) return fallback;
  const v = hit.params[key];
  return typeof v === "number" ? v : Number(v) || fallback;
}

function emaLengths(inds: ChartContext["indicators"]): [number, number] {
  const emas = inds.filter((i) => i.name.toUpperCase() === "EMA");
  const a = typeof emas[0]?.params.length === "number" ? emas[0].params.length : 21;
  const b = typeof emas[1]?.params.length === "number" ? emas[1].params.length : 55;
  return [Number(a), Number(b)];
}

/** Offline heuristic Pine Script draft from chart context. */
export function generatePine(ctx: ChartContext): GenerateResult {
  const wantsStrategy =
    /strateg|long|short|entr|exit|trade/i.test(ctx.intent) ||
    /strateg|long|short/i.test(ctx.notes);

  const rsiLen = numParam(ctx.indicators, "RSI", "length", 14);
  const ob = numParam(ctx.indicators, "RSI", "overbought", 70);
  const os = numParam(ctx.indicators, "RSI", "oversold", 30);
  const [emaFast, emaSlow] = emaLengths(ctx.indicators);
  const volMa = numParam(ctx.indicators, "Volume", "maLength", 20);

  const title = wantsStrategy
    ? `${ctx.symbol} RSI×EMA Reclaim Strategy`
    : `${ctx.symbol} RSI×EMA Signal Pack`;

  const tfLabel = ctx.timeframe.endsWith("m")
    ? ctx.timeframe
    : `${ctx.timeframe}m`;

  const agentNotes = [
    `Parsed ${ctx.exchange}:${ctx.symbol} on ${tfLabel} (${ctx.chartType}).`,
    `Mapped indicators → RSI(${rsiLen}), EMA(${emaFast}/${emaSlow}), Volume MA(${volMa}).`,
    wantsStrategy
      ? "Intent reads as a tradeable ruleset → drafting strategy() with entries/exits."
      : "Intent reads as signals/visuals → drafting indicator() with plots.",
    "Using Pine Script v5 templates (offline heuristic — no LLM API).",
    ctx.drawings.length
      ? `Noted ${ctx.drawings.length} drawing hint(s); left as comments for manual levels.`
      : "No drawing objects in context.",
  ];

  if (wantsStrategy) {
    const pine = `//@version=5
strategy("${title}", overlay=true, initial_capital=10000,
     default_qty_type=strategy.percent_of_equity, default_qty_value=10,
     commission_type=strategy.commission.percent, commission_value=0.05)

// ── Context (from chart bridge) ──────────────────────────────────────────
// Symbol: ${ctx.exchange}:${ctx.symbol} · TF: ${tfLabel}
// Notes: ${ctx.notes.replace(/\n/g, " ")}
${ctx.drawings.map((d) => `// Drawing: ${d}`).join("\n")}

// ── Inputs ───────────────────────────────────────────────────────────────
rsiLength   = input.int(${rsiLen}, "RSI Length", minval=2)
rsiOB       = input.int(${ob}, "RSI Overbought")
rsiOS       = input.int(${os}, "RSI Oversold")
emaFastLen  = input.int(${emaFast}, "Fast EMA")
emaSlowLen  = input.int(${emaSlow}, "Slow EMA (trend)")
volMaLen    = input.int(${volMa}, "Volume MA")
useVolFilter = input.bool(true, "Require volume > MA")

// ── Series ───────────────────────────────────────────────────────────────
rsiVal   = ta.rsi(close, rsiLength)
emaFast  = ta.ema(close, emaFastLen)
emaSlow  = ta.ema(close, emaSlowLen)
volMa    = ta.sma(volume, volMaLen)

trendUp  = close > emaSlow
rsiReclaim = ta.crossover(rsiVal, rsiOS)
priceReclaim = ta.crossover(close, emaFast)
volOk    = not useVolFilter or volume > volMa

longCond = trendUp and rsiReclaim and close > emaFast and volOk
// Alternate: allow same-bar reclaim combo
longAlt  = trendUp and rsiVal > rsiOS and priceReclaim and volOk

exitCond = ta.crossunder(rsiVal, rsiOB) or ta.crossunder(close, emaFast)

// ── Orders ───────────────────────────────────────────────────────────────
if longCond or longAlt
    strategy.entry("Long", strategy.long)

if exitCond
    strategy.close("Long")

// ── Visuals ──────────────────────────────────────────────────────────────
plot(emaFast, "EMA Fast", color=color.new(color.teal, 0), linewidth=2)
plot(emaSlow, "EMA Slow", color=color.new(color.orange, 0), linewidth=2)
plotshape(longCond or longAlt, title="Long", style=shape.triangleup,
     location=location.belowbar, color=color.new(color.lime, 0), size=size.small)
plotshape(exitCond and strategy.position_size > 0, title="Exit", style=shape.triangledown,
     location=location.abovebar, color=color.new(color.red, 0), size=size.small)

// Optional RSI pane helper (comment in if you split panes manually)
// plot(rsiVal, "RSI")
`;
    return { agentNotes, title, pine: pine.trim() + "\n", mode: "strategy" };
  }

  const pine = `//@version=5
indicator("${title}", overlay=true)

// ── Context (from chart bridge) ──────────────────────────────────────────
// Symbol: ${ctx.exchange}:${ctx.symbol} · TF: ${tfLabel}
// Notes: ${ctx.notes.replace(/\n/g, " ")}
${ctx.drawings.map((d) => `// Drawing: ${d}`).join("\n")}

rsiLength  = input.int(${rsiLen}, "RSI Length")
rsiOS      = input.int(${os}, "Oversold")
rsiOB      = input.int(${ob}, "Overbought")
emaFastLen = input.int(${emaFast}, "Fast EMA")
emaSlowLen = input.int(${emaSlow}, "Slow EMA")
volMaLen   = input.int(${volMa}, "Volume MA")

rsiVal  = ta.rsi(close, rsiLength)
emaFast = ta.ema(close, emaFastLen)
emaSlow = ta.ema(close, emaSlowLen)
volMa   = ta.sma(volume, volMaLen)

bullSignal = close > emaSlow and ta.crossover(rsiVal, rsiOS) and close > emaFast and volume > volMa
bearSignal = close < emaSlow and ta.crossunder(rsiVal, rsiOB) and close < emaFast

plot(emaFast, "EMA Fast", color=color.teal, linewidth=2)
plot(emaSlow, "EMA Slow", color=color.orange, linewidth=2)
plotshape(bullSignal, "Bull", shape.triangleup, location.belowbar, color.lime, size=size.small)
plotshape(bearSignal, "Bear", shape.triangledown, location.abovebar, color.red, size=size.small)

alertcondition(bullSignal, "Bull reclaim", "RSI/EMA bullish reclaim")
alertcondition(bearSignal, "Bear fade", "RSI/EMA bearish fade")
`;
  return { agentNotes, title, pine: pine.trim() + "\n", mode: "indicator" };
}

/** Best-effort parse of pasted freeform context into ChartContext fields. */
export function parseContextText(text: string, base: ChartContext): ChartContext {
  const ctx: ChartContext = {
    ...base,
    indicators: [...base.indicators.map((i) => ({ ...i, params: { ...i.params } }))],
    drawings: [...base.drawings],
  };
  const sym = text.match(/(?:Symbol|Ticker)\s*:\s*([A-Z0-9:.\-_]+)/i);
  if (sym) {
    const raw = sym[1];
    if (raw.includes(":")) {
      const [ex, s] = raw.split(":");
      ctx.exchange = ex;
      ctx.symbol = s;
    } else {
      ctx.symbol = raw;
    }
  }
  const tf = text.match(/Timeframe\s*:\s*(\d+\w?)/i);
  if (tf) ctx.timeframe = tf[1].replace(/m$/i, "");
  const intent = text.match(/Requested intent:\s*([\s\S]+?)(?:\n\n|$)/i);
  if (intent) ctx.intent = intent[1].trim();
  const notes = text.match(/Trader notes:\s*([\s\S]+?)(?:\n\n|Requested intent:|$)/i);
  if (notes) ctx.notes = notes[1].trim();
  return ctx;
}
