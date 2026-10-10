import pandas as pd
import pandera.errors
import pytest

from ms import db
from ms.collectors import metals_stooq, write


def test_parse_and_ingest(tmp_path, mem):
    p = tmp_path / "xauusd_d.csv"
    p.write_text("Date,Open,High,Low,Close\n2024-01-05,2040,2050,2030,2045\n2024-01-08,2045,2046,2020,2028\n")
    df = metals_stooq.parse(p, "XAUUSD")
    assert set(df.series_id) == {"XAUUSD.open", "XAUUSD.high", "XAUUSD.low", "XAUUSD.close"}
    # piątek 2024-01-05 -> zamknięcie sesji 17:00 ET (EST) = 22:00 UTC
    k = df.loc[(df.series_id == "XAUUSD.close") & (df.observed_at == "2024-01-05"), "known_at"].item()
    assert k == pd.Timestamp("2024-01-05 22:00")
    assert (df["flags"].str.contains("known_at_market_close")).all()
    assert write(mem, df) == 8 and write(mem, df) == 0


def test_format_change_is_hard_error(tmp_path):
    p = tmp_path / "xauusd_d.csv"
    p.write_text("Data,Otwarcie,Zamkniecie\n2024-01-05,1,2\n")
    with pytest.raises(pandera.errors.SchemaError):
        metals_stooq.parse(p, "XAUUSD")
