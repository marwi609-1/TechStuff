/** Preloaded TradingView-like chart context for the demo happy path. */
export type ChartContext = {
  symbol: string;
  exchange: string;
  timeframe: string;
  chartType: string;
  indicators: Array<{ name: string; params: Record<string, number | string> }>;
  drawings: string[];
  notes: string;
  intent: string;
};

export const SAMPLE_CONTEXT: ChartContext = {
  symbol: "BTCUSDT",
  exchange: "BINANCE",
  timeframe: "60",
  chartType: "candles",
  indicators: [
    { name: "RSI", params: { length: 14, overbought: 70, oversold: 30 } },
    { name: "EMA", params: { length: 21 } },
    { name: "EMA", params: { length: 55 } },
    { name: "Volume", params: { maLength: 20 } },
  ],
  drawings: [
    "Horizontal support near recent swing low",
    "Trendline connecting higher lows (last 12 bars)",
  ],
  notes:
    "Looking for long setups when RSI exits oversold and price reclaims the fast EMA with rising volume.",
  intent:
    "Write a Pine Script v5 strategy that goes long on RSI reclaim + close above EMA21, with EMA55 as trend filter and volume confirmation. Include basic exits and plot signals.",
};

export function formatContextAsText(ctx: ChartContext): string {
  const inds = ctx.indicators
    .map((i) => {
      const p = Object.entries(i.params)
        .map(([k, v]) => `${k}=${v}`)
        .join(", ");
      return `- ${i.name}(${p})`;
    })
    .join("\n");
  const draws = ctx.drawings.map((d) => `- ${d}`).join("\n");
  return [
    `Symbol: ${ctx.exchange}:${ctx.symbol}`,
    `Timeframe: ${ctx.timeframe}m`,
    `Chart: ${ctx.chartType}`,
    ``,
    `Indicators:`,
    inds,
    ``,
    `Drawings / levels:`,
    draws,
    ``,
    `Trader notes:`,
    ctx.notes,
    ``,
    `Requested intent:`,
    ctx.intent,
  ].join("\n");
}
