import asyncio
import aiohttp
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional


def iso_utc(value: Any, tz: Optional[str] = None) -> Optional[str]:
    """Normalise a source timestamp to an ISO-8601 UTC string, or None if unusable.

    Accepts datetime objects, epoch seconds/milliseconds and common string forms
    ('2026-10-01 10:45:01', '2026-10-01T10:45:01+02:00', '01/10/2026 17:57:50').
    Naive values are interpreted in the IANA timezone ``tz`` (e.g. "Europe/Lisbon") when given,
    otherwise as UTC.
    """
    if value is None or value == "":
        return None
    try:
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, (int, float)):
            v = float(value)
            dt = datetime.fromtimestamp(v / 1000 if v > 1e11 else v, tz=timezone.utc)
        else:
            s = str(value).strip().replace("Z", "+00:00")
            try:
                dt = datetime.fromisoformat(s)
            except ValueError:
                dt = None
                for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d.%m.%Y %H:%M:%S",
                            "%d.%m.%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                    try:
                        dt = datetime.strptime(s, fmt)
                        break
                    except ValueError:
                        continue
                if dt is None:
                    return None
        if dt.tzinfo is None:
            zone = timezone.utc
            if tz:
                try:
                    from zoneinfo import ZoneInfo
                    zone = ZoneInfo(tz)
                except Exception:   # tzdata missing (e.g. bare Windows): treat as UTC, error <= 2 h
                    zone = timezone.utc
            dt = dt.replace(tzinfo=zone)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return None


class BaseScraper:
    COUNTRY: str = ""
    CURRENCY: str = ""
    SOURCE: str = ""
    CONFIDENCE: float = 1.0  # 1.0 = official gov, <1.0 = community

    # Source grade shown to users (see docs/DATA_SOURCES_AUDIT.md):
    #   A = statutory real-time government feed (stations must report within minutes/hours)
    #   B = official government feed that is periodic/daily, or regulated national price
    #   C = commercial aggregator / resold data (no per-price timestamp)
    #   D = crowd-sourced / community reported
    #   L = locations only (no prices)
    GRADE: str = "C"

    # Minimum minutes between real refreshes of this source. Within that window main.py re-publishes
    # the previous result instead of calling the upstream again (politeness + speed). The CI chain runs
    # about every 15 minutes, so 12 = refresh on every run; slower sources override this.
    REFRESH_MINUTES: int = 12

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.fetched_at = datetime.now(timezone.utc).isoformat()

    async def fetch_stations(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def build_output(self, stations: List[Dict]) -> Dict:
        return {
            "meta": {
                "country": self.COUNTRY,
                "currency": self.CURRENCY,
                "source": self.SOURCE,
                "confidence": self.CONFIDENCE,
                "fetched_at": self.fetched_at,
                "station_count": len(stations),
            },
            "stations": stations,
        }

    def price_entry(self, fuel_type: str, price: float, unit: str = "L",
                    updated_at: Any = None, tz: Optional[str] = None) -> Dict:
        """Build a price record.

        ``updated_at`` must be the time the SOURCE says the price was set/reported.
        Pass nothing when the source gives no timestamp — it is then published as
        null (age unknown) instead of pretending the price is as fresh as our scrape.
        """
        return {
            "fuel_type": fuel_type,
            "price": price,
            "currency": self.CURRENCY,
            "unit": unit,
            "updated_at": iso_utc(updated_at, tz),
        }
