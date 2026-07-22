#!/usr/bin/env bash
set -euo pipefail
cd /root/bennix-investment-intelligence
python3 app.py scan
if git rev-parse --git-dir >/dev/null 2>&1; then
  git add index.html dashboard/index.html data/latest.json config.json
  if ! git diff --cached --quiet; then
    git commit -m "data: refresh intelligence $(date '+%F %H:%M WIB')"
    git push origin main
  fi
fi
printf '✅ Bennix Intelligence diperbarui: %s\n' "$(date '+%F %T')"
