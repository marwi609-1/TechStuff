export type LintSeverity = "error" | "warning" | "info";

export type LintIssue = {
  severity: LintSeverity;
  line: number | null;
  code: string;
  message: string;
};

export type LintResult = {
  ok: boolean;
  issues: LintIssue[];
  summary: string;
};

function lineOf(source: string, index: number): number {
  return source.slice(0, index).split("\n").length;
}

/** Lightweight Pine Script v5 style checks for the demo. */
export function lintPine(source: string): LintResult {
  const issues: LintIssue[] = [];
  const lines = source.split("\n");
  const trimmed = source.trim();

  if (!trimmed) {
    return {
      ok: false,
      issues: [
        {
          severity: "error",
          line: null,
          code: "empty",
          message: "Script is empty.",
        },
      ],
      summary: "1 error",
    };
  }

  // //@version=
  const versionMatch = source.match(/\/\/\s*@version\s*=\s*(\d+)/);
  if (!versionMatch) {
    issues.push({
      severity: "error",
      line: 1,
      code: "missing-version",
      message: "Missing //@version=5 directive (required for Pine v5).",
    });
  } else if (versionMatch[1] !== "5") {
    issues.push({
      severity: "warning",
      line: lineOf(source, versionMatch.index ?? 0),
      code: "old-version",
      message: `Found //@version=${versionMatch[1]}; demo targets v5.`,
    });
  }

  // declaration
  const hasIndicator = /\bindicator\s*\(/.test(source);
  const hasStrategy = /\bstrategy\s*\(/.test(source);
  const hasLibrary = /\blibrary\s*\(/.test(source);
  if (!hasIndicator && !hasStrategy && !hasLibrary) {
    issues.push({
      severity: "error",
      line: null,
      code: "no-declaration",
      message:
        "No indicator(), strategy(), or library() declaration found.",
    });
  }
  if (hasIndicator && hasStrategy) {
    issues.push({
      severity: "error",
      line: null,
      code: "dual-declaration",
      message: "Script cannot declare both indicator() and strategy().",
    });
  }

  // common typos / legacy
  const legacy: Array<[RegExp, string, string]> = [
    [/\bstudy\s*\(/, "legacy-study", "study() is deprecated; use indicator()."],
    [/\bsecurity\s*\(/, "legacy-security", "Prefer request.security() in Pine v5."],
    [/\btransp\s*=/, "legacy-transp", "transp= is deprecated; use color.new(..., transp)."],
  ];
  for (const [re, code, message] of legacy) {
    const m = source.match(re);
    if (m) {
      issues.push({
        severity: "warning",
        line: lineOf(source, m.index ?? 0),
        code,
        message,
      });
    }
  }

  // undeclared / suspicious identifiers (heuristic)
  const declared = new Set<string>();
  // inputs, vars, consts, functions roughly
  const declRes = [
    /\b(?:var(?:ip)?|const)?\s*(?:float|int|bool|string|color|line|label|box|table)?\s*([A-Za-z_][\w]*)\s*=/g,
    /\b([A-Za-z_][\w]*)\s*=\s*input[\w.]*\s*\(/g,
    /\b(?:method\s+)?([A-Za-z_][\w]*)\s*\([^)]*\)\s*=>/g,
  ];
  for (const re of declRes) {
    let m: RegExpExecArray | null;
    while ((m = re.exec(source))) declared.add(m[1]);
  }
  // built-ins / namespaces we ignore
  const builtins = new Set([
    "true",
    "false",
    "na",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "time",
    "bar_index",
    "hl2",
    "hlc3",
    "ohlc4",
    "strategy",
    "indicator",
    "library",
    "plot",
    "plotshape",
    "plotchar",
    "barcolor",
    "bgcolor",
    "hline",
    "fill",
    "alertcondition",
    "input",
    "ta",
    "math",
    "str",
    "color",
    "array",
    "matrix",
    "map",
    "request",
    "ticker",
    "syminfo",
    "timeframe",
    "session",
    "location",
    "shape",
    "size",
    "display",
    "format",
    "xloc",
    "yloc",
    "style",
    "position",
    "long",
    "short",
    "if",
    "else",
    "for",
    "while",
    "switch",
    "type",
    "export",
    "import",
    "and",
    "or",
    "not",
    "to",
    "by",
  ]);

  // Flag simple bare identifiers used on RHS that look undeclared
  // Only check lines with assignment or plot/if for demo signal
  const useRe = /\b([a-z][A-Za-z0-9_]*)\b/g;
  const suspicious = new Set(["myRsi", "fastEma", "slowEma", "volMa", "longCond", "shortCond"]);
  // Also detect common undeclared typos users introduce when editing
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*\/\//.test(line)) continue;
    let m: RegExpExecArray | null;
    const local = new RegExp(useRe.source, "g");
    while ((m = local.exec(line))) {
      const id = m[1];
      if (builtins.has(id) || declared.has(id)) continue;
      if (suspicious.has(id) && !declared.has(id)) {
        issues.push({
          severity: "error",
          line: i + 1,
          code: "undeclared",
          message: `Possible undeclared identifier '${id}'.`,
        });
      }
    }
  }

  // strategy without entry/exit
  if (hasStrategy) {
    if (!/\bstrategy\.(entry|order)\s*\(/.test(source)) {
      issues.push({
        severity: "warning",
        line: null,
        code: "no-entry",
        message: "strategy() found but no strategy.entry/order — no trades will fire.",
      });
    }
  }

  // missing plot for indicator
  if (hasIndicator && !/\bplot\s*\(/.test(source) && !/\bplotshape\s*\(/.test(source)) {
    issues.push({
      severity: "info",
      line: null,
      code: "no-plot",
      message: "indicator() with no plot/plotshape — nothing will render on the chart.",
    });
  }

  // unbalanced parentheses (rough)
  let depth = 0;
  for (let i = 0; i < source.length; i++) {
    const c = source[i];
    if (c === "(") depth++;
    if (c === ")") depth--;
    if (depth < 0) {
      issues.push({
        severity: "error",
        line: lineOf(source, i),
        code: "paren",
        message: "Unbalanced parentheses (extra ')').",
      });
      break;
    }
  }
  if (depth > 0) {
    issues.push({
      severity: "error",
      line: lines.length,
      code: "paren",
      message: "Unbalanced parentheses (missing ')').",
    });
  }

  const errors = issues.filter((i) => i.severity === "error").length;
  const warnings = issues.filter((i) => i.severity === "warning").length;
  const infos = issues.filter((i) => i.severity === "info").length;
  const parts: string[] = [];
  if (errors) parts.push(`${errors} error${errors === 1 ? "" : "s"}`);
  if (warnings) parts.push(`${warnings} warning${warnings === 1 ? "" : "s"}`);
  if (infos) parts.push(`${infos} info`);
  const summary = parts.length ? parts.join(", ") : "All checks passed";

  return { ok: errors === 0, issues, summary };
}
