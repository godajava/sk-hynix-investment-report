"""fetch_quote 복원/교차검증 로직 단위 테스트 (네트워크 없음). 실행: python3 tests/test_fetch_quote.py"""
import os
import sys
import time
import calendar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_quote as fq  # noqa: E402


def kst_ts(date, hhmm):
    y, m, d = map(int, date.split("-"))
    hh, mm = int(hhmm[:2]), int(hhmm[2:])
    return calendar.timegm((y, m, d, hh, mm, 0)) - 9 * 3600


def mk_q(rows):
    return {k: [r[i] for r in rows] for i, k in enumerate(["open", "high", "low", "close", "volume"])}


def test_parse_skips_none():
    ts = [kst_ts("2026-10-08", "0900"), kst_ts("2026-10-12", "0900")]
    q = mk_q([(1, 2, 0, 1.5, 10), (None, None, None, None, None)])
    days, skipped = fq.parse_bars(ts, q)
    assert [d["date"] for d in days] == ["2026-10-08"] and skipped == ["2026-10-12"]


def test_intraday_aggregation_and_merge():
    rows, ts = [], []
    for hhmm, o, h, l, c, v in [("0900", 164, 165, 163, 164.5, 100), ("1000", 164.5, 165.3, 162, 163, 200),
                                ("1520", 163, 163, 160.5, 160.5, 300)]:
        ts.append(kst_ts("2026-10-12", hhmm)); rows.append((o, h, l, c, v))
    ts.append(kst_ts("2026-10-12", "1525")); rows.append((None,) * 5)
    ts.append(kst_ts("2026-10-13", "0900")); rows.append((150, 152, 149, 151, 50))
    idays = fq.daily_from_intraday(ts, mk_q(rows))
    b = idays["2026-10-12"]
    assert (b["open"], b["high"], b["low"], b["close"], b["volume"]) == (164, 165.3, 160.5, 160.5, 600)
    days = [{"date": "2026-10-08", "open": 1, "high": 1, "low": 1, "close": 168.1, "volume": 1},
            {"date": "2026-10-13", "open": 150, "high": 152, "low": 149, "close": 151, "volume": 50}]
    merged, added = fq.merge_missing_days(days, idays)
    assert added == ["2026-10-12"]
    assert [d["date"] for d in merged] == ["2026-10-08", "2026-10-12", "2026-10-13"]
    assert merged[1]["synthetic"] is True


def test_pick_prev_missing_bar_uses_tradingview():
    days = [{"date": "2026-10-08", "close": 1681000}, {"date": "2026-10-13", "close": 1506000}]
    prev, src, warn = fq.pick_prev(days, "2026-10-13", 1605000)
    assert prev == 1605000 and src == "tradingview" and warn


def test_pick_prev_consistent():
    days = [{"date": "2026-10-12", "close": 1605000}, {"date": "2026-10-13", "close": 1506000}]
    prev, src, warn = fq.pick_prev(days, "2026-10-13", 1605000)
    assert prev == 1605000 and src == "yahoo-daily+tradingview-ok" and warn is None


def test_pick_prev_no_tv():
    days = [{"date": "2026-10-12", "close": 1605000}, {"date": "2026-10-13", "close": 1506000}]
    assert fq.pick_prev(days, "2026-10-13", None)[:2] == (1605000, "yahoo-daily")


def test_pick_prev_after_close_next_day_not_started():
    days = [{"date": "2026-10-12", "close": 1605000}]
    assert fq.pick_prev(days, "2026-10-13", None)[0] == 1605000


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("ok", n)
