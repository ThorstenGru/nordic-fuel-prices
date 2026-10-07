import sys, os
from datetime import date
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scrapers.montenegro import parse_cap_page, merge_with_cap
from scrapers.kosovo import parse_post, newest_post_url

ME = ("<p>Datum ažuriranja: </p><p>07.10.2026</p> Cijene će vrijediti do 11.10.2026. u 23:59h."
      "<td>Eurodizel</td><td>1.96€ / L</td><td>Benzin BMB 95</td><td>1.77€ / L</td>"
      "<td>Benzin BMB 98</td><td>1.81€ / L</td>")
TODAY = date(2026, 10, 7)


def test_me_parse_ok():
    c = parse_cap_page(ME, TODAY)
    assert c["date"] == "2026-10-07" and c["prices"] == {"DIESEL": 1.96, "95": 1.77, "98": 1.81}


def test_me_stale_or_implausible():
    assert parse_cap_page(ME, date(2026, 12, 1)) is None
    assert parse_cap_page(ME.replace("1.96", "9.96"), TODAY) is None


def test_xk_parse_and_stale():
    h = ("<p>produktit Dizel është: 1.88 € për litër; produktit Benzinë është: 1.46 € për litër;"
         " produktit Gas është: 0.74 € për litër</p>")
    assert parse_post(h, date(2026, 10, 6), TODAY)["prices"] == {"DIESEL": 1.88, "95": 1.46, "LPG": 0.74}
    assert parse_post(h, date(2026, 4, 7), TODAY) is None
    d, _u = newest_post_url("x https://minti.rks-gov.net/news/cmimet-maksimale-te-lejuara-per-derivatet-e-naftes-dates-07-04-2026/ y")
    assert d == date(2026, 4, 7)


def test_merge_keeps_anwb_price():
    st = [{"id": "a", "lat": 42.0, "lon": 19.0, "brand": "Lukoil", "name": "L", "prices":
           [{"fuel_type": "95", "price": 1.70, "currency": "EUR", "unit": "L", "octane": 95, "updated_at": None}]},
          {"id": "b", "lat": 42.5, "lon": 19.5, "brand": "Shell", "name": "S", "prices": []}]
    cap = {"date": "2026-10-07", "prices": {"DIESEL": 1.96, "95": 1.77}}
    out, rep = merge_with_cap("ME", st, cap)
    assert len(out) == 2
    a = next(s for s in out if s["id"] == "a")
    b = next(s for s in out if s["id"] == "b")
    p95 = next(p for p in a["prices"] if p["fuel_type"] == "95")
    assert p95["price"] == 1.70 and p95.get("basis") != "regulated_max"
    assert next(p for p in a["prices"] if p["fuel_type"] == "DIESEL")["basis"] == "regulated_max"
    assert all(p["basis"] == "regulated_max" for p in b["prices"]) and len(b["prices"]) == 2
    assert merge_with_cap("ME", st, None)[0] is st
