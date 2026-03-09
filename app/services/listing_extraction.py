import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import httpx


@dataclass
class ExtractionResult:
    data: Dict[str, Any]
    confidence: Dict[str, float]
    sources: Dict[str, str]
    message: str


def _safe_get(d: Dict[str, Any], path: Tuple[str, ...]) -> Optional[Any]:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _parse_json_ld(html: str) -> Dict[str, Any]:
    results: Dict[str, Any] = {}
    scripts = re.findall(
        r"<script[^>]*type=\"application/ld\+json\"[^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for raw in scripts:
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue

        nodes = parsed if isinstance(parsed, list) else [parsed]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            addr = node.get("address")
            if isinstance(addr, dict):
                street = addr.get("streetAddress")
                city = addr.get("addressLocality")
                state = addr.get("addressRegion")
                postal = addr.get("postalCode")
                if street and city and state and postal:
                    results.update(
                        {
                            "address": street,
                            "city": city,
                            "state": state,
                            "zip_code": postal,
                        }
                    )

            geo = node.get("geo")
            if isinstance(geo, dict):
                lat = geo.get("latitude")
                lon = geo.get("longitude")
                if lat is not None and lon is not None:
                    results.update({"latitude": lat, "longitude": lon})

            # Some sites store basic facts here.
            name = node.get("name")
            if name and "address" not in results:
                results["raw_name"] = name

    return results


def _parse_basic_numbers(html: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def grab(pattern: str) -> Optional[str]:
        m = re.search(pattern, html, flags=re.IGNORECASE)
        return m.group(1) if m else None

    price = grab(r"\$\s*([0-9][0-9,]{2,})")
    if price:
        try:
            out["price"] = float(price.replace(",", ""))
        except Exception:
            pass

    beds = grab(r"([0-9]{1,2}(?:\.[0-9])?)\s*beds?")
    if beds:
        try:
            out["beds"] = int(float(beds))
        except Exception:
            pass

    baths = grab(r"([0-9]{1,2}(?:\.[0-9])?)\s*baths?")
    if baths:
        try:
            out["baths"] = float(baths)
        except Exception:
            pass

    sqft = grab(r"([0-9][0-9,]{2,})\s*(?:sq\s*ft|sqft)")
    if sqft:
        try:
            out["sqft"] = float(sqft.replace(",", ""))
        except Exception:
            pass

    year = grab(r"(19[0-9]{2}|20[0-2][0-9])\s*(?:built|year built)")
    if year:
        try:
            out["year_built"] = int(year)
        except Exception:
            pass

    return out


async def extract_listing(url: str) -> ExtractionResult:
    # 1. Try RapidAPI Zillow.com API (Free tier available)
    rapidapi_key = os.getenv("RAPIDAPI_KEY")
    if rapidapi_key and "zillow.com" in url.lower():
        try:
            # Extract ZPID from URL
            # e.g., https://www.zillow.com/homedetails/.../17154238_zpid/
            zpid_match = re.search(r"/(\d+)_zpid", url)
            if zpid_match:
                zpid = zpid_match.group(1)
                async with httpx.AsyncClient(timeout=20) as client:
                    res = await client.get(
                        "https://zillow-com1.p.rapidapi.com/property",
                        params={"propertyKey": zpid},
                        headers={
                            "X-RapidAPI-Key": rapidapi_key,
                            "X-RapidAPI-Host": "zillow-com1.p.rapidapi.com"
                        }
                    )
                    if res.status_code == 200:
                        payload = res.json()
                        extracted: Dict[str, Any] = {}
                        
                        # Map RapidAPI response fields to our schema
                        address = payload.get("address", {})
                        extracted["address"] = address.get("streetAddress")
                        extracted["city"] = address.get("city")
                        extracted["state"] = address.get("state")
                        extracted["zip_code"] = address.get("zipcode")
                        
                        extracted["price"] = payload.get("price")
                        extracted["beds"] = payload.get("bedrooms")
                        extracted["baths"] = payload.get("bathrooms")
                        extracted["sqft"] = payload.get("livingArea")
                        extracted["year_built"] = payload.get("yearBuilt")
                        
                        # Only keep non-None values
                        extracted = {k: v for k, v in extracted.items() if v is not None}
                        
                        return ExtractionResult(
                            data=extracted,
                            confidence={k: 0.95 for k in extracted.keys()},
                            sources={k: "rapidapi" for k in extracted.keys()},
                            message="Extracted via RapidAPI"
                        )
        except Exception as e:
            # Fall through to other extraction methods if API fails
            pass

    # 2. Try generic Listing API template (if configured)
    api_url_template = os.getenv("LISTING_API_URL_TEMPLATE")
    api_key = os.getenv("LISTING_API_KEY")
    api_header = os.getenv("LISTING_API_KEY_HEADER", "X-API-Key")

    if api_url_template and api_key:
        try:
            api_url = api_url_template.format(url=url)
            async with httpx.AsyncClient(timeout=20) as client:
                res = await client.get(api_url, headers={api_header: api_key})
                res.raise_for_status()
                payload = res.json()

            extracted: Dict[str, Any] = {}
            if isinstance(payload, dict):
                extracted.update(payload.get("property", payload))

            return ExtractionResult(
                data=extracted,
                confidence={k: 0.9 for k in extracted.keys()},
                sources={k: "listing_api" for k in extracted.keys()},
                message="Extracted via listings API",
            )
        except Exception:
            pass

    html = ""
    scraperapi_key = os.getenv("SCRAPERAPI_KEY")

    if scraperapi_key:
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                res = await client.get(
                    "http://api.scraperapi.com",
                    params={"api_key": scraperapi_key, "url": url, "render": "true"},
                )
                res.raise_for_status()
                html = res.text
        except Exception:
            pass

    if not html:
        try:
            async with httpx.AsyncClient(
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                },
                follow_redirects=True,
            ) as client:
                res = await client.get(url)
                res.raise_for_status()
                html = res.text
        except Exception as e:
            return ExtractionResult(
                data={},
                confidence={},
                sources={},
                message=f"Failed to fetch listing: {e}",
            )

    jsonld = _parse_json_ld(html)
    basic = _parse_basic_numbers(html)

    data: Dict[str, Any] = {}
    confidence: Dict[str, float] = {}
    sources: Dict[str, str] = {}

    for k, v in {**jsonld, **basic}.items():
        if v is None:
            continue
        data[k] = v
        sources[k] = "scrape"
        confidence[k] = 0.6 if k in basic else 0.75

    msg = "Extracted from page" if data else "Could not extract data from page"
    return ExtractionResult(data=data, confidence=confidence, sources=sources, message=msg)
