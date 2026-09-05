# Validation notes

- Date: 2026-09-05 (Europe/Berlin)
- Server: `bun run dev` → http://localhost:3847
- Health: `/api/health` → `{ ok: true, mode: "demo" }`
- Generate with sample context produces Pine v5 strategy; lint summary: All checks passed
- Screenshot: `artifacts/demo-ui.png` (headless Chrome, 1440×900)
- Happy path: page auto-loads sample + generates on boot

## Manual re-check
1. Open http://localhost:3847
2. Confirm chips show BINANCE:BTCUSDT · 60m · RSI/EMA/Volume
3. Confirm agent notes + Pine draft + green lint
4. Edit Pine (remove `//@version=5`) → Re-lint → expect error

- Video: `artifacts/demo-ui.mp4` (UI capture for PR validation)
