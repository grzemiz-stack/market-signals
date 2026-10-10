#!/bin/zsh
# Pełna bramka projektu. Każda nowa kontrola -> dopisz tutaj.
set -eu
cd "${0:A:h}/.."
echo "[0] żaden job nie pisze teraz do bazy"; for l in logs/locks/*.lock(N); do
  /usr/bin/lockf -k -s -t 0 "$l" /usr/bin/true || { echo "trwa job ${l:t:r} — testy kopiują bazę; poczekaj (tools/health.sh)"; exit 1; }; done
echo "[1] składnia Pythona";        uv run --frozen python -m compileall -q src tests >/dev/null
echo "[2] plist launchd (szablony -> build/launchd)"; /usr/bin/python3 tools/jobctl.py render build/launchd >/dev/null; plutil -lint build/launchd/*.plist
echo "[3] data/ i logs/ ignorowane"; for p in data/x logs/x .env; do git check-ignore -q "$p"; done
echo "[4] reguły rolowania krzywej"; uv run --frozen python - <<'PY'
import sys; sys.path.insert(0, "src")
from datetime import date
from snapshot_raw import last_trade_cl, last_trade_bz, candidate_contracts
# znane daty z kalendarza CME
assert last_trade_cl(2026, 11) == date(2026, 10, 20), last_trade_cl(2026, 11)
assert last_trade_bz(2026, 11) == date(2026, 9, 30), last_trade_bz(2026, 11)
assert last_trade_bz(2026, 12) == date(2026, 10, 30), last_trade_bz(2026, 12)
assert candidate_contracts("CL", date(2026, 10, 6), 1)[0][0] == "CLX26.NYM"
assert candidate_contracts("BZ", date(2026, 10, 6), 1)[0][0] == "BZZ26.NYM"
assert candidate_contracts("CL", date(2026, 10, 21), 1)[0][0] == "CLZ26.NYM"
print("ok")
PY
echo "[5] check_snapshot na syntetycznym manifeście"; uv run --frozen python - <<'PY'
import json, sys, tempfile
from datetime import date
from pathlib import Path
sys.path.insert(0, "src")
import check_snapshot as cs
D = "2026-10-06"
def e(source, filename, path="", sha="x"):
    return {"source": source, "filename": filename, "snapshot_date": D, "sha256": sha, "path": path}
full = [e("curve", f"{r}{m}.NYM.csv") for r in ("CL", "BZ") for m in "ABCDEF"]
full += [e("gpr", "data_gpr_daily_recent.xls"), e("tpu", "tpu_web_latest.xlsx")]
full += [e("coinmetrics", f"asset-metrics_{a}_c01_p01.json", f"data/raw/coinmetrics/{D}/x") for a in ("btc", "eth")]
def run(entries):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(json.dumps(x) for x in entries))
    cs.MANIFEST = Path(f.name)
    return cs.find_missing(date.fromisoformat(D))
assert run(full) == [], run(full)
assert run(full[1:]) == ["krzywa CL: 5/6"], run(full[1:])
assert run([x for x in full if x["source"] != "gpr"]) == ["gpr data_gpr_daily_recent.xls"]
# backfill nie zastępuje dziennego przyrostu
bf = [x for x in full if x["source"] != "coinmetrics"] + [e("coinmetrics", "asset-metrics_btc_c01_p01.json", "data/raw/coinmetrics/backfill/x")]
assert run(bf) == ["coinmetrics daily btc", "coinmetrics daily eth"], run(bf)
# nieudane pobranie (bez sha) to brak; unchanged (bez path) to obecność
assert run([x for x in full if x["source"] != "tpu"] + [{**e("tpu", "tpu_web_latest.xlsx"), "sha256": None}]) == ["tpu tpu_web_latest.xlsx"]
print("ok")
PY
echo "[6] idempotentność Store (sha per source/subdir/filename)"; uv run --frozen python - <<'PY'
import sys, tempfile
from datetime import date
from pathlib import Path
sys.path.insert(0, "src")
import snapshot_raw as sr
tmp = Path(tempfile.mkdtemp())
sr.ROOT, sr.RAW = tmp, tmp / "data" / "raw"
sr.MANIFEST = sr.RAW / "manifest.jsonl"
st = sr.Store(date(2026, 10, 6))
assert st.save("cm", "a.json", b"X", "u", 200, subdir="backfill")["unchanged"] is False
assert st.save("cm", "a.json", b"Y", "u", 200)["unchanged"] is False
st2 = sr.Store(date(2026, 10, 7))  # nowa instancja czyta manifest z dysku
assert st2.save("cm", "a.json", b"Y", "u", 200)["unchanged"] is True    # dzienny vs dzienny
assert st2.save("cm", "a.json", b"X", "u", 200)["unchanged"] is False   # backfill nie jest odniesieniem
assert not (sr.RAW / "cm" / "2026-10-07" / "a.json").read_bytes() == b"Y"
print("ok")
PY
echo "[8] mapa zależności: tekst z literatury nietknięty"; python3 tools/check_mapa.py
echo "[7] pytest (rdzeń + testy na data/market.duckdb; w tym tylko-lokalnie i joby)"; MS_REQUIRE_DB=1 uv run --frozen pytest -q
echo "[9] stan na żywo = repo (plisty zainstalowane i załadowane, Ollama tylko 127.0.0.1)"; tools/check_runtime.sh
echo "BRAMKA ZIELONA"
