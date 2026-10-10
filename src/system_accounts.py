"""Konta „system” (etap 5 krok 5) — CLI i krok joba „system”.

uv run src/system_accounts.py create [--start YYYY-MM-DD]   # tworzy „system” i „system_ostrozny” (pomija istniejące)
uv run src/system_accounts.py run                           # job: decyzje dla gotowych dni + próg D9 (idempotentne)
uv run src/system_accounts.py status                        # decyzje i wartość kont
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, paper as pp, rules as R, system  # noqa: E402

log = logging.getLogger("system")


def accounts(pcon) -> pd.DataFrame:
    system.init(pcon)
    return pcon.execute("""SELECT a.*, s.variant, s.dd_limit FROM paper_accounts a JOIN paper_system s ON s.account_id = a.id
                           ORDER BY a.id""").df()


ALARM_STATE = db.ROOT / "logs" / "state" / "alarms.json"


def alarm(name: str, msgs: list[str]) -> None:
    """Alarm = wpis w logu (codziennie, póki trwa) + powiadomienie macOS przy wejściu w stan alarmu. Nic więcej."""
    import json
    import subprocess

    st = json.loads(ALARM_STATE.read_text()) if ALARM_STATE.exists() else {}
    active = sorted(m.split(" (")[0].rsplit(" ", 1)[0] for m in msgs)      # rodzaj alarmu bez liczby
    for m in msgs:
        log.warning("ALARM %s: %s — tylko informacja, decyzje konta bez zmian (wyłączenie wyłącznie regułą D9)", name, m)
    new = [m for m, k in zip(msgs, active) if k not in st.get(name, [])]
    if new:
        text = f"{name}: " + "; ".join(new) + ". Decyzje konta bez zmian."
        subprocess.run(["osascript", "-e", f'display notification "{text}" with title "market-signals: ALARM konta"'],
                       check=False)
    st[name] = active
    ALARM_STATE.parent.mkdir(parents=True, exist_ok=True)
    ALARM_STATE.write_text(json.dumps(st, ensure_ascii=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["create", "run", "status"])
    ap.add_argument("--start")
    ap.add_argument("--paper-db", default=str(pp.PAPER_DB))
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.FileHandler(db.ROOT / "logs" / "system.log"), logging.StreamHandler()])
    pcon = pp.connect(a.paper_db)
    system.init(pcon)
    if a.cmd == "create":
        mcon = db.connect()
        start = pd.Timestamp(a.start or system.now_utc().date())
        for name in system.ACCOUNTS:
            if pcon.execute("SELECT count(*) FROM paper_accounts WHERE name=?", [name]).fetchone()[0]:
                log.info("%s: już istnieje", name)
                continue
            log.info("%s: utworzone (id %d, start %s, wariant %s)", name, system.create(pcon, mcon, name, start),
                     start.date(), system.ACCOUNTS[name])
        return 0
    mcon = db.connect(read_only=True)
    data = R.RuleData.load(mcon)
    for _, acc in accounts(pcon).iterrows():
        if a.cmd == "run":
            for line in system.run_account(pcon, data, acc) or [f"{acc['name']}: brak nowych decyzji"]:
                log.info(line)
            alarm(acc["name"], system.alarms(pp.replay(pcon, data.book, acc).values))
        else:
            st = pp.replay(pcon, data.book, acc)
            dec = pcon.execute("SELECT decision_date, exec_date, kind, why FROM paper_system_decisions WHERE account_id=? "
                               "ORDER BY decision_date", [int(acc["id"])]).df()
            print(f"# {acc['name']} ({acc['variant']}), start {acc['start_date']}: wartość {st.values.iloc[-1]:,.2f} zł, "
                  f"próg D9 {acc['dd_limit']:.1%}")
            print(dec.to_string(index=False) if len(dec) else "(brak decyzji)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
