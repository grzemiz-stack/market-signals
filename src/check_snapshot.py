"""Test kompletności dzisiejszego snapshotu.

W dzień roboczy (pn–pt; bez kalendarza świąt) wymaga udanego wpisu w manifeście
(zapisany plik albo unchanged=true) z dzisiejszą snapshot_date dla:
- curve: 6 kontraktów CL i 6 kontraktów BZ
- gpr: data_gpr_daily_recent.xls
- tpu: tpu_web_latest.xlsx
- coinmetrics daily: asset-metrics_{btc,eth}_*.json (poza backfill/ i initial/)
COMEX i Baker Hughes są ręczne (skrzynki w data/inbox/) i nie są sprawdzane.
Braki -> powiadomienie macOS (osascript) + kod wyjścia 1.
"""

from __future__ import annotations

import os

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "raw" / "manifest.jsonl"

REQUIRED_FILES = {
    "gpr": ("data_gpr_daily_recent.xls",),
    "tpu": ("tpu_web_latest.xlsx",),
}
CM_ASSETS = ("btc", "eth")


def today_ok_entries(today: date) -> list[dict]:
    if not MANIFEST.exists():
        return []
    out = []
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("snapshot_date") == today.isoformat() and e.get("sha256"):
            out.append(e)
    return out


def find_missing(today: date) -> list[str]:
    entries = today_ok_entries(today)
    names = {(e["source"], e["filename"]) for e in entries}
    missing = []

    # yfinance-owe CSV kontraktów: liczymy po prefiksie (symbole zależą od rolla)
    for root in ("CL", "BZ"):
        n = len({f for s, f in names if s == "curve" and f.startswith(root) and f.endswith(".NYM.csv")})
        if n < 6:
            missing.append(f"krzywa {root}: {n}/6")

    for source, files in REQUIRED_FILES.items():
        missing += [f"{source} {f}" for f in files if (source, f) not in names]

    # dzienny przyrost CM: wpisy z dziś, ale nie z backfillu/initial (te mają path z podkatalogiem)
    for a in CM_ASSETS:
        ok = any(
            e["source"] == "coinmetrics"
            and e["filename"].startswith(f"asset-metrics_{a}_")
            and not any(x in e.get("path", "") for x in ("/backfill/", "/initial/"))
            for e in entries
        )
        if not ok:
            missing.append(f"coinmetrics daily {a}")
    return missing


def notify(title: str, msg: str) -> None:
    script = f"display notification {json.dumps(msg)} with title {json.dumps(title)} sound name \"Basso\""
    subprocess.run(["osascript", "-e", script], check=False)


def main() -> int:
    # data uruchomienia joba (snapshot_daily.sh); bez niej przejście przez północ (usypianie, nadrabianie) dawało
    # fałszywy błąd: snapshot z dnia D sprawdzany jako D+1 (2026-10-08)
    today = date.fromisoformat(os.environ["MS_SNAPSHOT_DATE"]) if os.environ.get("MS_SNAPSHOT_DATE") else date.today()
    if today.weekday() >= 5:
        print(f"{today}: weekend, skip")
        return 0
    missing = find_missing(today)
    if missing:
        msg = "Brak: " + "; ".join(missing)
        print(f"{today}: {msg}")
        notify("market-signals: niekompletny snapshot", msg)
        return 1
    print(f"{today}: OK (curve, gpr, tpu, coinmetrics daily)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
