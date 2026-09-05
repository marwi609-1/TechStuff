const $ = (id) => document.getElementById(id);

const els = {
  context: $("context"),
  pine: $("pine"),
  chips: $("meta-chips"),
  notes: $("agent-notes"),
  lintList: $("lint-list"),
  lintEmpty: $("lint-empty"),
  lintSummary: $("lint-summary"),
  btnGenerate: $("btn-generate"),
  btnSample: $("btn-sample"),
  btnClear: $("btn-clear"),
  btnLint: $("btn-lint"),
  btnCopy: $("btn-copy"),
  toast: $("toast"),
};

let samplePayload = null;

function toast(msg) {
  els.toast.textContent = msg;
  els.toast.classList.add("show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => els.toast.classList.remove("show"), 1800);
}

function renderChips(ctx) {
  if (!ctx) {
    els.chips.innerHTML = "";
    return;
  }
  const tf = String(ctx.timeframe).endsWith("m")
    ? ctx.timeframe
    : `${ctx.timeframe}m`;
  const inds = (ctx.indicators || []).map((i) => i.name).join(" · ");
  els.chips.innerHTML = [
    chip("Symbol", `${ctx.exchange}:${ctx.symbol}`),
    chip("TF", tf),
    chip("Chart", ctx.chartType),
    chip("Indicators", inds || "—"),
  ].join("");
}

function chip(label, value) {
  return `<span class="chip"><strong>${label}</strong> ${escapeHtml(value)}</span>`;
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderNotes(notes) {
  els.notes.innerHTML = "";
  (notes || ["No notes"]).forEach((n) => {
    const li = document.createElement("li");
    li.textContent = n;
    els.notes.appendChild(li);
  });
}

function renderLint(lint) {
  const issues = lint?.issues || [];
  els.lintList.innerHTML = "";
  if (!issues.length) {
    els.lintList.hidden = true;
    els.lintEmpty.hidden = false;
    els.lintEmpty.textContent = lint?.summary === "All checks passed"
      ? "✓ All checks passed — ready to paste into TradingView Pine Editor."
      : "No lint results yet.";
    els.lintSummary.textContent = lint?.summary || "Idle";
    els.lintSummary.className =
      lint?.ok ? "status-ok" : lint ? "status-warn" : "status-warn";
    if (lint?.ok) {
      els.lintSummary.className = "status-ok";
    }
    return;
  }
  els.lintEmpty.hidden = true;
  els.lintList.hidden = false;
  for (const issue of issues) {
    const li = document.createElement("li");
    li.innerHTML = `
      <span class="sev sev-${issue.severity}">${issue.severity}</span>
      <span class="line-no">${issue.line != null ? `L${issue.line}` : "—"}</span>
      <span class="msg">${escapeHtml(issue.message)}</span>`;
    els.lintList.appendChild(li);
  }
  els.lintSummary.textContent = lint.summary;
  els.lintSummary.className = lint.ok
    ? issues.some((i) => i.severity === "warning")
      ? "status-warn"
      : "status-ok"
    : "status-bad";
}

async function loadSample() {
  const res = await fetch("/api/sample");
  samplePayload = await res.json();
  els.context.value = samplePayload.text;
  renderChips(samplePayload.context);
  toast("Sample chart context loaded");
}

async function generate() {
  els.btnGenerate.disabled = true;
  els.btnGenerate.textContent = "Generating…";
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        text: els.context.value,
        context: samplePayload?.context,
      }),
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    els.pine.value = data.pine;
    renderNotes(data.agentNotes);
    renderChips(data.context);
    renderLint(data.lint);
    els.btnLint.disabled = false;
    els.btnCopy.disabled = false;
    toast(`Drafted ${data.mode}: ${data.title}`);
  } catch (e) {
    toast(String(e.message || e));
  } finally {
    els.btnGenerate.disabled = false;
    els.btnGenerate.textContent = "Generate Pine Script";
  }
}

async function relint() {
  const res = await fetch("/api/lint", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ pine: els.pine.value }),
  });
  const lint = await res.json();
  renderLint(lint);
  toast(lint.summary);
}

async function copyPine() {
  try {
    await navigator.clipboard.writeText(els.pine.value);
    toast("Pine Script copied");
  } catch {
    els.pine.select();
    document.execCommand("copy");
    toast("Pine Script copied");
  }
}

els.btnSample.addEventListener("click", loadSample);
els.btnClear.addEventListener("click", () => {
  els.context.value = "";
  els.chips.innerHTML = "";
});
els.btnGenerate.addEventListener("click", generate);
els.btnLint.addEventListener("click", relint);
els.btnCopy.addEventListener("click", copyPine);
els.pine.addEventListener("input", () => {
  els.btnLint.disabled = !els.pine.value.trim();
  els.btnCopy.disabled = !els.pine.value.trim();
});

// Boot: preload sample then auto-generate for one-click demo feel
(async () => {
  await loadSample();
  await generate();
})();
