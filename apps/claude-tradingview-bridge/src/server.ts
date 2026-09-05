import { SAMPLE_CONTEXT, formatContextAsText } from "./mock-context";
import { generatePine, parseContextText } from "./pine-generate";
import { lintPine } from "./pine-lint";

const PORT = Number(process.env.PORT ?? 3847);
const publicDir = `${import.meta.dir}/../public`;

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function contentType(path: string): string {
  if (path.endsWith(".html")) return "text/html; charset=utf-8";
  if (path.endsWith(".css")) return "text/css; charset=utf-8";
  if (path.endsWith(".js")) return "application/javascript; charset=utf-8";
  if (path.endsWith(".svg")) return "image/svg+xml";
  if (path.endsWith(".png")) return "image/png";
  if (path.endsWith(".json")) return "application/json";
  return "application/octet-stream";
}

Bun.serve({
  port: PORT,
  async fetch(req) {
    const url = new URL(req.url);

    if (url.pathname === "/api/health") {
      return json({ ok: true, mode: "demo", port: PORT });
    }

    if (url.pathname === "/api/sample") {
      return json({
        context: SAMPLE_CONTEXT,
        text: formatContextAsText(SAMPLE_CONTEXT),
      });
    }

    if (url.pathname === "/api/generate" && req.method === "POST") {
      try {
        const body = (await req.json()) as { text?: string; context?: typeof SAMPLE_CONTEXT };
        const base = body.context ?? SAMPLE_CONTEXT;
        const ctx = body.text ? parseContextText(body.text, base) : base;
        const result = generatePine(ctx);
        const lint = lintPine(result.pine);
        return json({ ...result, context: ctx, lint });
      } catch (e) {
        return json({ error: String(e) }, 400);
      }
    }

    if (url.pathname === "/api/lint" && req.method === "POST") {
      try {
        const body = (await req.json()) as { pine?: string };
        return json(lintPine(body.pine ?? ""));
      } catch (e) {
        return json({ error: String(e) }, 400);
      }
    }

    let path = url.pathname === "/" ? "/index.html" : url.pathname;
    // prevent path traversal
    path = path.replace(/\.\./g, "");
    const file = Bun.file(`${publicDir}${path}`);
    if (await file.exists()) {
      return new Response(file, {
        headers: { "content-type": contentType(path) },
      });
    }
    return new Response("Not found", { status: 404 });
  },
});

console.log(`Claude ↔ TradingView Bridge demo → http://localhost:${PORT}`);
