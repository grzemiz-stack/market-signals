"""Zalecenia reguł etapu 5 na dziś -> tabela rules_today (etap 4C; krok joba snapshot po predict_daily).

uv run src/rules_today.py

Dla dnia decyzji D (ostatni dzień roboczy USA <= dziś; dane znane w D 22:00 UTC) i każdego konta gry: wagi docelowe
wariantu (równy podział = zwycięzca D7, V1–V3 — rules.target_weights, kod zamrożony), bieżące wagi konta (ceny znane w D),
czy reguła każe dziś rebalansować i dlaczego, zlecenia w zł do wag docelowych (progi jak w backteście).
To INFORMACJA: nic nie jest składane automatycznie (konta „system” prowadzi job system wg własnego harmonogramu).
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import db, momentum as mm, paper as pp, rules as R, system  # noqa: E402
from ms.trading import GAME_ASSETS  # noqa: E402

VARIANTS = ("rowny_podzial_4", *R.VARIANTS)


def decision_day(book, today) -> pd.Timestamp:
    d = pd.Timestamp(today).normalize()
    while d.weekday() >= 5 or d in book._hol:
        d -= pd.Timedelta(days=1)
    return d


def targets(data: R.RuleData, D: pd.Timestamp, variant: str) -> tuple[dict, dict]:
    if variant == "rowny_podzial_4":
        elig = mm.assets_with_history(data.book, D, GAME_ASSETS)
        return {a: 1 / len(elig) for a in elig}, {"sigma": {}, "sigma_src": {}, "exposure": {}}
    return R.target_weights(data, D, variant)


def build(mcon, pcon, today=None) -> pd.DataFrame:
    data = R.RuleData.load(mcon)
    book = data.book
    D = decision_day(book, today or pd.Timestamp.now(tz="UTC").tz_localize(None))
    accounts = pcon.execute("SELECT * FROM paper_accounts ORDER BY id").df()
    sysvar = dict(pcon.execute("SELECT account_id, variant FROM paper_system").fetchall()) if pcon.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name='paper_system'").fetchone()[0] else {}
    rows = []
    tgt = {v: targets(data, D, v) for v in VARIANTS}
    month_end = mm.rebalance_dates(book, D.replace(day=1), D + pd.offsets.MonthEnd(0), "M")[-1]
    prev_end = mm.rebalance_dates(book, (D.replace(day=1) - pd.Timedelta(days=1)).replace(day=1),
                                  D.replace(day=1) - pd.Timedelta(days=1), "M")[-1]
    prev_expo = {v: R.target_weights(data, prev_end, v)[1]["exposure"] for v in R.VARIANTS}
    for _, acc in accounts.iterrows():
        st = pp.replay(pcon, book, acc, until=D)
        cur = R.known_weights(st.acc, data, D)
        total = st.values.iloc[-1] if len(st.values) else float(acc["start_cash"])
        own = sysvar.get(int(acc["id"]))
        for v in VARIANTS:
            target, snap = tgt[v]
            if v == "rowny_podzial_4":
                decision = D == month_end and D.month in (3, 6, 9, 12)
                why = "koniec kwartału" if decision else ""
                nxt = next(d for d in mm.rebalance_dates(book, D, D + pd.Timedelta(days=100), "M") if d.month in (3, 6, 9, 12))
            else:
                decision = D == month_end
                why = "; ".join(R.rebalance_triggers(D, cur, target, snap["exposure"], prev_expo[v])) if decision else ""
                nxt = month_end
            for a in sorted(set(target) | set(cur)):
                w, c = target.get(a, 0.0), cur.get(a, 0.0)
                rows.append({"D": D.date(), "account_id": int(acc["id"]), "account": acc["name"], "variant": v,
                             "konto_wykonuje": v == own, "asset": a, "target_w": w, "current_w": c,
                             "exposure": snap["exposure"].get(a), "sigma": snap["sigma"].get(a),
                             "sigma_src": snap["sigma_src"].get(a), "decision_day": bool(decision),
                             "next_decision": pd.Timestamp(nxt).date(), "rebalance": bool(why), "why": why,
                             "order_pln": (w - c) * total, "account_value": total})
    return pd.DataFrame(rows)


def main() -> int:
    mcon = db.connect()
    pcon = duckdb.connect(str(pp.PAPER_DB), read_only=True)
    df = build(mcon, pcon).assign(built_at=system.now_utc(), rules_hash=R.definitions_hash())
    mcon.register("rt", df)
    mcon.execute("CREATE OR REPLACE TABLE rules_today AS SELECT * FROM rt")
    mcon.unregister("rt")
    print(f"rules_today: {len(df)} wierszy, D = {df['D'].iloc[0] if len(df) else '—'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
