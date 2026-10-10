import pandas as pd

from ms.collectors import fred


def test_vintage_windows_cover_all_without_overlap():
    vd = [str(d.date()) for d in pd.date_range("2000-01-01", periods=4000)]
    w = fred.vintage_windows(vd)
    assert len(w) == 3 and w[0][0] == vd[0] and w[-1][1] == "9999-12-31"
    for (a, b), (c, _) in zip(w, w[1:]):
        assert pd.Timestamp(b) + pd.Timedelta(days=1) == pd.Timestamp(c)


def test_first_release_strictly_after_period_end():
    ends = pd.Series(pd.to_datetime(["2024-01-31", "2024-02-29"]))
    rd = pd.Series(["2024-01-31", "2024-02-13", "2024-03-12"])
    assert list(fred.first_release_after(ends, rd)) == [pd.Timestamp("2024-02-13"), pd.Timestamp("2024-03-12")]


def test_pre_archive_ignores_release_dates_far_after_period():
    """Tabela wydań zaczyna się lata po obserwacji -> mediana opóźnienia, nie data wydania (błąd z 2026-10-06: VIX 1990–2010)."""
    vint = pd.DataFrame({"date": pd.to_datetime(["1990-01-02", "2010-11-19", "2010-11-22"]),
                         "realtime_start": pd.to_datetime(["2010-11-22", "2010-11-22", "2010-11-23"]),
                         "value": [17.2, 18.0, 18.5]})
    out = fred.build("THREEFYTP10", vint, "D", "17:00", "public_domain", pd.Series(["2014-04-16", "2014-04-17"]))  # seria bez zasady dnia notowania
    rule = out[(out.observed_at == "1990-01-02") & (out["flags"] == "known_at_rule")]
    assert len(rule) == 1 and rule.known_at.iloc[0] < pd.Timestamp("1990-01-10")


def test_market_close_series_known_on_observation_day_and_revisions_keep_alfred():
    vint = pd.DataFrame({"date": pd.to_datetime(["2024-03-14", "2024-03-14", "2024-03-15"]),
                         "realtime_start": pd.to_datetime(["2024-03-18", "2024-04-01", "2024-03-18"]),
                         "value": [1.09, 1.10, 1.08]})
    out = fred.build("DEXUSEU", vint, "D", "16:15", "public_domain", pd.Series(dtype=str))
    d14 = out[out.observed_at == "2024-03-14"].sort_values("known_at")
    assert d14.known_at.iloc[0] == pd.Timestamp("2024-03-14 16:00")       # 12:00 EDT = 16:00 UTC, dzień notowania
    assert d14["flags"].iloc[0] == "known_at_market_close"
    assert d14.known_at.iloc[1] == pd.Timestamp("2024-04-01 20:15")       # rewizja: data ALFRED


def test_incremental_revision_of_old_observation_does_not_get_early_date():
    vint = pd.DataFrame({"date": pd.to_datetime(["2024-01-10", "2024-03-14"]),
                         "realtime_start": pd.to_datetime(["2024-03-11", "2024-03-15"]), "value": [1.2, 1.1]})
    out = fred.build("DEXUSEU", vint, "D", "16:15", "public_domain", pd.Series(dtype=str), incremental=True, since="2024-03-11")
    old = out[out.observed_at == "2024-01-10"]
    assert old.known_at.iloc[0] >= pd.Timestamp("2024-03-11")             # nie cofnięta do 2024-01-10


def test_treasury_yields_flagged_publication():
    vint = pd.DataFrame({"date": pd.to_datetime(["2024-03-14"]), "realtime_start": pd.to_datetime(["2024-03-15"]), "value": [1.9]})
    out = fred.build("DFII10", vint, "D", "16:15", "public_domain", pd.Series(dtype=str))
    assert "known_at_publication_unverified_close" in out["flags"].iloc[0] and out.known_at.iloc[0] > pd.Timestamp("2024-03-15")
