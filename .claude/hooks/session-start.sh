#!/bin/bash
# SessionStart-Hook für Claude Code on the web: installiert die Python-Abhängigkeiten
# von apps/powerlab (numpy, pytest, ruff), damit Tests und Linter sofort laufen.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

# Editable install: `import powerlab` funktioniert überall, Codeänderungen ohne Reinstall.
# pip ist idempotent; bereits installierte Pakete werden übersprungen.
python3 -m pip install --quiet --disable-pip-version-check --root-user-action=ignore \
  -e "apps/powerlab[dev]"
