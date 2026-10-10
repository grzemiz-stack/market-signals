"""Reguła publikacji COT vs oficjalny harmonogram CFTC 2026 (pobrany 2026-10-06 ze strony CFTC)."""

from datetime import date, timedelta

from ms.collectors import cot

SCHEDULE_2026 = {
    1: [5, 9, 16, 23, 30], 2: [6, 13, 20, 27], 3: [6, 13, 20, 27], 4: [3, 10, 17, 24], 5: [1, 8, 15, 22, 29],
    6: [5, 12, 22, 26], 7: [6, 10, 17, 24, 31], 8: [7, 14, 21, 28], 9: [4, 11, 18, 25], 10: [2, 9, 16, 23, 30],
    11: [6, 16, 20, 30], 12: [4, 11, 18, 28],
}


def test_rule_reproduces_cftc_2026_schedule():
    official = [date(2026, m, d) for m, ds in SCHEDULE_2026.items() for d in ds]
    tue = date(2025, 12, 30)  # raport, którego publikacja przypada na 2026-01-05*
    computed = []
    while len(computed) < len(official):
        computed.append(cot.release_date(tue))
        tue += timedelta(days=7)
    assert computed == official


def test_shutdown_reports_flagged_uncertain():
    import pandas as pd
    k, f = cot.known_at(pd.Series(pd.to_datetime(["2019-01-08", "2019-06-04"])))
    assert list(f) == ["known_at_uncertain", "known_at_rule"]
    assert k.iloc[0] >= pd.Timestamp("2019-03-08")
