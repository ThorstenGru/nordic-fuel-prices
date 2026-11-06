import os
import sys
import unittest
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import elpris  # noqa: E402


def rows(day, price, n=24, off="+01:00"):
    step = 60 // (n // 24)
    return [{"SEK_per_kWh": price(i), "time_start": f"{day}T{i * step // 60:02d}:{i * step % 60:02d}:00{off}"} for i in range(n)]


class Pure(unittest.TestCase):
    def test_stockholm_today(self):
        # 23:30 UTC on 5 Jan is already 6 Jan in Sweden (CET); 22:30 UTC on 5 Jul is 6 Jul (CEST); 22:30 UTC 5 Jan is still 5 Jan
        self.assertEqual(elpris.stockholm_today(datetime(2026, 1, 5, 23, 30, tzinfo=timezone.utc)), date(2026, 1, 6))
        self.assertEqual(elpris.stockholm_today(datetime(2026, 7, 5, 22, 30, tzinfo=timezone.utc)), date(2026, 7, 6))
        self.assertEqual(elpris.stockholm_today(datetime(2026, 1, 5, 22, 30, tzinfo=timezone.utc)), date(2026, 1, 5))
        # DST switch 2026-03-29 01:00 UTC
        self.assertEqual(elpris.stockholm_today(datetime(2026, 3, 28, 22, 30, tzinfo=timezone.utc)), date(2026, 3, 28))
        self.assertEqual(elpris.stockholm_today(datetime(2026, 3, 29, 22, 30, tzinfo=timezone.utc)), date(2026, 3, 30))

    def test_parse_day_hourly_from_15min(self):
        d = elpris.parse_day(rows("2026-11-06", lambda i: 1.0 + (i // 4) / 10, n=96))
        self.assertEqual(d["n"], 96)
        self.assertEqual(len(d["hourly"]), 24)
        self.assertAlmostEqual(d["hourly"][5], 1.5)
        self.assertAlmostEqual(d["mean"], 1.0 + sum(range(24)) / 24 / 10)

    def test_parse_day_rejects_bad(self):
        self.assertIsNone(elpris.parse_day([]))
        self.assertIsNone(elpris.parse_day(None))
        self.assertIsNone(elpris.parse_day(rows("2026-11-06", lambda i: 999.0)))
        self.assertIsNone(elpris.parse_day(rows("2026-11-06", lambda i: "x")))
        self.assertIsNotNone(elpris.parse_day(rows("2026-11-06", lambda i: -0.05)))   # negative prices are real

    def test_dst_fall_back_has_25_hours(self):
        r = rows("2026-10-24", lambda i: 1.0)[:0]
        for h in range(25):
            off = "+02:00" if h < 3 else "+01:00"
            hh = h if h < 3 else h - 1
            r.append({"SEK_per_kWh": 1.0, "time_start": f"2026-10-25T{hh:02d}:00:00{off}"})
        self.assertEqual(len(elpris.parse_day(r)["hourly"]), 25)

    def test_month_mean_weights_rows_and_flags_partial(self):
        days = {"2026-02-01": [1.0, 24], "2026-02-02": [3.0, 96]}
        m = elpris.month_mean(days, "2026-02")
        self.assertAlmostEqual(m["mean"], (24 + 288) / 120)
        self.assertFalse(m["complete"])
        full = {f"2026-02-{d:02d}": [2.0, 24] for d in range(1, 29)}
        self.assertTrue(elpris.month_mean(full, "2026-02")["complete"])
        self.assertIsNone(elpris.month_mean(days, "2026-03"))
        self.assertTrue(elpris.month_mean({f"2025-12-{d:02d}": [1, 24] for d in range(1, 32)}, "2025-12")["complete"])

    def test_invoice_fixture_se4(self):
        # Sep 2026 SE4: skelleftea Medelspotpris 1.20202 vs equal-weight mean of API rows 1.20125 (tolerance 0.002)
        days = {f"2026-09-{d:02d}": [1.20125, 96] for d in range(1, 31)}
        self.assertAlmostEqual(elpris.month_mean(days, "2026-09")["mean"], 1.20202, delta=0.002)

    def test_seasonal_band(self):
        monthly = {"2022": [3.0] + [None] * 11, "2023": [1.0] + [None] * 11, "2024": [1.2] + [None] * 11,
                   "2025": [1.4] + [None] * 11, "2026": [1.1] + [None] * 11}
        s = elpris.seasonal(monthly, None)["1"]
        self.assertEqual(s["n"], 4)                       # latest 4 years only: 2023-2026
        self.assertAlmostEqual(s["mean"], 1.175)
        self.assertLess(s["hi"], 1.4)                     # percentile band, 2022 crisis year excluded
        self.assertEqual(elpris.seasonal(monthly, "2026-01")["1"]["n"], 3)   # partial month skipped; window stays 2023..2026, 2022 never enters
        late = {"2022": [None] * 11 + [2.7], "2023": [None] * 11 + [.65], "2024": [None] * 11 + [.69], "2025": [None] * 11 + [.8], "2026": [1.0] * 10 + [None] * 2}
        self.assertEqual(elpris.seasonal(late, None)["12"]["n"], 3)         # December: no 2022 crisis value
        self.assertEqual(elpris.seasonal({"2025": [2.0] + [None] * 11}, None)["1"]["lo"], 2.0)

    def test_build_area_rollover_and_shape(self):
        today = date(2026, 11, 6)
        day = {"mean": 1.5, "n": 96, "hourly": [1.5] * 24}
        days = {f"2026-10-{d:02d}": [1.0, 24] for d in range(1, 32)}
        days["2026-09-30"] = [9.0, 24]                   # older than previous month: dropped
        days["2026-11-05"] = [2.0, 96]
        days["2026-11-06"] = [3.0, 96]
        a = elpris.build_area({}, {"2026": [None] * 9 + [None] * 3}, today, day, None, days)
        self.assertNotIn("2026-09-30", a["days"])
        self.assertEqual(a["monthly"]["2026"][9], 1.0)    # October complete
        self.assertAlmostEqual(a["monthly"]["2026"][10], 2.5)
        self.assertEqual(a["partial"], {"month": "2026-11", "days": 2})
        self.assertIsNone(a["tomorrow"])
        self.assertEqual(len(a["today"]["sek"]), 24)
        self.assertEqual(a["seasonal"]["10"]["n"], 1)
        self.assertNotIn("11", a["seasonal"])             # only partial data for November

    def test_incomplete_previous_month_does_not_overwrite(self):
        today = date(2026, 11, 6)
        day = {"mean": 1.5, "n": 96, "hourly": [1.5] * 24}
        days = {f"2026-10-{d:02d}": [5.0, 24] for d in (1, 2, 3)}
        days["2026-11-06"] = [3.0, 96]
        a = elpris.build_area({"monthly": {"2026": [None] * 9 + [9.0, None, None]}}, {"2026": [None] * 9 + [1.56718, None, None]}, today, day, None, days)
        self.assertEqual(a["monthly"]["2026"][9], 1.56718)  # seed wins over prev and over the 3-day mean
        b = elpris.build_area({"monthly": {"2026": [None] * 9 + [9.0, None, None]}}, {}, today, day, None, days)
        self.assertEqual(b["monthly"]["2026"][9], 9.0)      # no seed: prev kept, not the 3-day mean 5.0
        c = elpris.build_area({}, {}, today, day, None, days)
        self.assertIsNone(c["monthly"]["2026"][9])          # nothing known: stays empty, never a partial mean
        self.assertEqual(c["partial"]["month"], "2026-11")

    def test_seed_extension_reaches_current_year(self):
        today = date(2026, 11, 6)
        day = {"mean": 1.5, "n": 96, "hourly": [1.5] * 24}
        a = elpris.build_area({"monthly": {"2026": [1.0] + [None] * 11}}, {"2026": [1.0, 2.0] + [None] * 10}, today, day, None, {"2026-11-06": [3.0, 96]})
        self.assertEqual(a["monthly"]["2026"][1], 2.0)


if __name__ == "__main__":
    unittest.main()
