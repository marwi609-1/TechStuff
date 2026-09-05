# Claude ↔ TradingView Bridge (Demo MVP)

Offline Bun demo inspired by a Claude Code ↔ TradingView workflow. Paste or load mock chart context, generate a Pine Script draft, and get simple lint feedback — no OAuth, no API keys.

## Quick start

```bash
cd /workspace/claude-tradingview-bridge
bun install
bun run dev
```

Open **http://localhost:3847** (or the port printed in the terminal).

## Happy path

1. Mock chart context is preloaded (BTCUSDT · 1H · RSI / EMA / Volume).
2. Click **Generate Pine Script**.
3. Review the agent notes + draft on the right.
4. Check the **Lint** panel; click **Re-lint** after editing the script.
5. Use **Copy** to grab the Pine source.

## Scripts

| Command        | Description                |
|----------------|----------------------------|
| `bun run dev`  | Hot-reload dev server      |
| `bun run start`| Production-style serve     |

## Layout

```
claude-tradingview-bridge/
├── PLAN.md
├── README.md
├── package.json
├── public/          # UI
├── src/             # Bun server + pine engine
└── artifacts/       # screenshots / demo notes
```

## Notes

- Pine generation is **template/heuristic** — impressive offline, not a live LLM.
- Demo mode only; nothing talks to TradingView’s APIs.
