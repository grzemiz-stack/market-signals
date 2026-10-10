"""Raport reports/features-{data}.md: per cecha start, % NaN, grupa; częstości bazowe etykiet; przykładowe analogie.

% NaN surowej wartości = dni decyzji aktywa od startu cechy bez wartości (bez forward-fill poza tym, co daje panel).
% NaN z-score = dodatkowo pierwszy rok (rozgrzewka okna).
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ms import analogs, db, labels  # noqa: E402
from ms.features import asset_calendar  # noqa: E402


def main() -> int:
    con = db.connect(db.DB_PATH, read_only=True)
    f = con.execute("""SELECT asset, feature, grp, any_value(short_history) AS short_history, min(date) AS start,
                              max(date) AS koniec, count(*) AS n, count(value_z) AS nz
                       FROM features_daily GROUP BY ALL ORDER BY asset, grp, feature""").df()
    end = pd.Timestamp(f["koniec"].max())
    cal = {a: asset_calendar(a, end) for a in f["asset"].unique()}
    f["dni"] = [int((cal[a] >= pd.Timestamp(s)).sum()) for a, s in zip(f["asset"], f["start"])]
    f["nan_raw_%"] = (100 * (1 - f["n"] / f["dni"])).round(1)
    f["nan_z_%"] = (100 * (1 - f["nz"] / f["dni"])).round(1)
    f = f.drop(columns=["n", "nz", "dni", "koniec"])

    br = labels.base_rates(con)
    out = [f"# Cechy i analogie — {date.today()}", "",
           "Chwila decyzji D 22:00 UTC. z-score kroczący 3 lata (min 1 rok). `short_history` = poza analogiami.", "",
           "## Częstość bazowa etykiet (5 dni, ±1,5σ)", "", br.to_markdown(index=False, floatfmt=".3f"), "",
           "## Cechy", "", f.to_markdown(index=False), ""]
    for a in ("XAU", "WTI", "BTC"):
        out.append(analogs.to_markdown(analogs.find(con, a, date.today())))
    p = db.ROOT / "reports" / f"features-{date.today()}.md"
    p.write_text("\n".join(out))
    print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
