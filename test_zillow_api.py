import asyncio
import httpx
import re
import json

async def main():
    url = "https://www.zillow.com/homedetails/3241-Naylor-Rd-San-Diego-CA-92173/17154238_zpid/"
    # Try the Zillow GraphQL API approach using a standard User-Agent from a mobile device
    # Sometimes mobile User-Agents bypass PerimeterX on the initial HTML load
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Upgrade-Insecure-Requests": "1"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
        res = await client.get(url)
        print(f"Status (Mobile UA): {res.status_code}")
        if res.status_code == 200:
            print("Successfully bypassed with Mobile UA!")
            return

    # Try pretending to be Googlebot
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "*/*"
    }
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=20) as client:
        res = await client.get(url)
        print(f"Status (Googlebot UA): {res.status_code}")
        if res.status_code == 200:
            print("Successfully bypassed with Googlebot UA!")
            return

asyncio.run(main())
