import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx


@dataclass
class EnrichmentResult:
    data: Dict[str, Any]
    confidence: Dict[str, float]
    sources: Dict[str, str]


def _has_address_bits(data: Dict[str, Any]) -> bool:
    return bool(data.get("address") and data.get("city") and data.get("state"))


async def enrich_property(data: Dict[str, Any]) -> EnrichmentResult:
    out: Dict[str, Any] = {}
    conf: Dict[str, float] = {}
    sources: Dict[str, str] = {}

    if not _has_address_bits(data):
        return EnrichmentResult(data=out, confidence=conf, sources=sources)

    if data.get("zip_code") and data.get("walk_score") and data.get("school_rating"):
        return EnrichmentResult(data=out, confidence=conf, sources=sources)

    use_nominatim = os.getenv("NOMINATIM_ENABLED", "true").lower() in ("1", "true", "yes")
    if not use_nominatim:
        return EnrichmentResult(data=out, confidence=conf, sources=sources)

    query = f"{data.get('address')}, {data.get('city')}, {data.get('state')}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "addressdetails": 1, "limit": 1},
                headers={"User-Agent": "demander/0.1 (local dev)"},
            )
            res.raise_for_status()
            arr = res.json()

        if isinstance(arr, list) and arr:
            first = arr[0]
            addr = first.get("address") or {}

            if not data.get("zip_code") and addr.get("postcode"):
                out["zip_code"] = str(addr.get("postcode"))
                conf["zip_code"] = 0.7
                sources["zip_code"] = "nominatim"

            if not data.get("city") and (addr.get("city") or addr.get("town") or addr.get("village")):
                out["city"] = addr.get("city") or addr.get("town") or addr.get("village")
                conf["city"] = 0.7
                sources["city"] = "nominatim"

            if not data.get("state") and addr.get("state"):
                out["state"] = addr.get("state")
                conf["state"] = 0.7
                sources["state"] = "nominatim"

            if first.get("lat") and first.get("lon"):
                if not data.get("latitude"):
                    out["latitude"] = float(first.get("lat"))
                    conf["latitude"] = 0.7
                    sources["latitude"] = "nominatim"
                if not data.get("longitude"):
                    out["longitude"] = float(first.get("lon"))
                    conf["longitude"] = 0.7
                    sources["longitude"] = "nominatim"

    except Exception:
        return EnrichmentResult(data=out, confidence=conf, sources=sources)

    return EnrichmentResult(data=out, confidence=conf, sources=sources)
