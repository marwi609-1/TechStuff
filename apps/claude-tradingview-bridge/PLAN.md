# PLAN — Claude ↔ TradingView Bridge (MVP Demo)

## Goal
Single-user, offline demo showing a Claude Code–inspired workflow: paste or load mock TradingView chart/indicator context → generate an agent-style Pine Script draft → surface simple compile/lint feedback. No real TradingView OAuth or external LLM keys.

## MVP Scope (in)
- Preloaded mock chart context (symbol, timeframe, indicators, notes)
- One-click **Generate Pine Script** (template / heuristic engine)
- Agent-style reasoning blurb + drafted `.pine` source
- Lint panel: `@version`, undeclared ids, `strategy`/`indicator` declaration, common typos
- Clean dark trading UI with a single happy path
- Local Bun server (`bun run dev`)

## Out of scope
- Real TradingView OAuth / chart sync
- Live LLM API calls (optional future)
- Multi-user auth, persistence, billing
- Publishing scripts to TradingView

## Stack
- **Runtime:** Bun 1.4+
- **Server:** Bun.serve (static + `/api/generate`, `/api/lint`)
- **UI:** Vanilla HTML/CSS/JS (no build step) — demo-ready, fast
- **Generation:** Heuristic templates keyed off mock context fields
- **Lint:** Rule-based Pine v5 checks

## Acceptance criteria
1. `cd /workspace/claude-tradingview-bridge && bun install && bun run dev` starts without errors
2. Opening the local URL shows preloaded mock context; one click generates Pine
3. Lint panel reports issues (and clears them after fix / regenerate)
4. Works fully offline (no API keys)
5. `PLAN.md` + `README.md` present; screenshot under `artifacts/` when available

## Screenshot / video validation
- Capture the main UI with context pane + generated Pine + lint results
- Save to `artifacts/demo-ui.png` (or note URL + steps if headless capture fails)
- Happy-path check: Load sample → Generate → see green/amber lint → Copy script

## Future (post-MVP)
- Optional Anthropic/OpenAI backend for richer drafts
- Real TradingView webhook / chart snapshot paste formats
- Diff view between regenerations
