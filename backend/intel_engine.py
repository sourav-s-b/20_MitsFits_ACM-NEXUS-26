"""
intel_engine.py
===============
NexusPath Intelligence Aggregator
Gathers multi-source real-world data (weather, traffic, news, social)
for a given lat/lon and produces a structured RiskIntelReport for the risk model.

Sources:
  1. Weather  — OpenWeatherMap API
  2. Traffic  — TomTom Routing API (delay in seconds)
  3. News     — NewsAPI.org (headlines mentioning the city/route)
  4. Social   — Reddit RSS + public incident feeds (no auth needed)
"""

import asyncio
import os
import time
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

TOMTOM_KEY  = os.getenv("TOMTOM_API_KEY", "")
OWM_KEY     = os.getenv("OPENWEATHER_API_KEY", "")
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

# ---------------------------------------------------------------------------
# Reverse-geocode: lat/lon → city name (used to filter news/social)
# ---------------------------------------------------------------------------

async def _get_city_name(lat: float, lon: float) -> str:
    """Use Nominatim (free, no key) to resolve city name."""
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?lat={lat}&lon={lon}&format=json&zoom=10"
        )
        async with httpx.AsyncClient(headers={"User-Agent": "NexusPath/1.0"}) as client:
            resp = await client.get(url, timeout=5.0)
            data = resp.json()
        address = data.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("state_district")
            or "Unknown"
        )
        return city
    except Exception:
        return "Unknown"


# ---------------------------------------------------------------------------
# MODULE 1 — WEATHER (OpenWeatherMap)
# ---------------------------------------------------------------------------

async def fetch_weather_intel(lat: float, lon: float) -> dict:
    """Fetches live weather and computes a 0–1 risk score."""
    if not OWM_KEY:
        return {
            "available": False,
            "score": 0.05,
            "description": "clear sky (no API key)",
            "temp_c": 28.0,
            "humidity": 60,
            "wind_kph": 12.0,
            "visibility_km": 10.0,
            "rain_1h_mm": 0.0,
        }
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={OWM_KEY}&units=metric"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
            data = resp.json()

        if data.get("cod") != 200:
            return {"available": False, "score": 0.0}

        rain_1h    = data.get("rain", {}).get("1h", 0.0)
        wind_speed = data.get("wind", {}).get("speed", 0.0)
        visibility = data.get("visibility", 10000) / 1000  # km
        description = data["weather"][0]["description"]
        temp_c     = data["main"]["temp"]
        humidity   = data["main"]["humidity"]

        # Composite risk score
        rain_score   = min(rain_1h / 20.0, 1.0)
        wind_score   = min(wind_speed / 25.0, 1.0)
        vis_score    = 1.0 - min(visibility / 10.0, 1.0)
        score        = round(rain_score * 0.5 + wind_score * 0.3 + vis_score * 0.2, 3)

        return {
            "available": True,
            "score": score,
            "description": description,
            "temp_c": round(temp_c, 1),
            "humidity": humidity,
            "visibility_km": round(visibility, 1),
            "wind_kph": round(wind_speed * 3.6, 1),
            "rain_1h_mm": rain_1h,
        }
    except Exception as e:
        return {"available": False, "score": 0.0, "error": str(e)}


# ---------------------------------------------------------------------------
# MODULE 2 — TRAFFIC (TomTom)
# ---------------------------------------------------------------------------

async def fetch_traffic_intel(lat: float, lon: float, dest_lat: float, dest_lon: float) -> dict:
    """Fetches traffic delay estimate and computes a 0–1 congestion score."""
    if not TOMTOM_KEY:
        return {"available": False, "score": 0.0, "delay_min": 0}
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute"
            f"/{lat},{lon}:{dest_lat},{dest_lon}/json"
            f"?key={TOMTOM_KEY}&travelMode=truck&traffic=true"
        )
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=8.0)
            data = resp.json()

        if "routes" not in data or not data["routes"]:
            return {"available": False, "score": 0.0, "delay_min": 0}

        summary       = data["routes"][0].get("summary", {})
        delay_seconds = summary.get("trafficDelayInSeconds", 0)
        delay_min     = round(delay_seconds / 60, 1)
        # Score: 0 → <5 min delay, 1 → 60+ min delay
        score         = round(min(delay_seconds / 3600, 1.0), 3)

        return {"available": True, "score": score, "delay_min": delay_min}
    except Exception as e:
        return {"available": False, "score": 0.0, "delay_min": 0, "error": str(e)}


# ---------------------------------------------------------------------------
# MODULE 3 — NEWS (NewsAPI.org / GNews fallback)
# ---------------------------------------------------------------------------

def _news_sentiment(title: str) -> str:
    """Simple keyword-based sentiment on a headline."""
    neg_words = [
        "flood", "accident", "crash", "block", "jam", "closure", "protest",
        "riot", "landslide", "storm", "strike", "hazard", "collision", "damage",
    ]
    for w in neg_words:
        if w in title.lower():
            return "negative"
    return "neutral"


def _relevance_score(title: str, city: str) -> float:
    """Estimate how relevant a headline is to the current route city."""
    city_low  = city.lower()
    title_low = title.lower()
    if city_low in title_low:
        return 0.9
    road_words = ["nh-", "sh-", "highway", "road", "bridge", "route", "bypass"]
    if any(w in title_low for w in road_words):
        return 0.6
    return 0.3


async def fetch_news_intel(city: str) -> list:
    """
    Fetches recent news headlines related to the route city.
    Uses NewsAPI.org if NEWS_API_KEY is set, otherwise falls back to 
    a free RSS headline scrape from a public news source.
    """
    articles = []

    # --- Primary: NewsAPI.org ---
    if NEWS_API_KEY:
        try:
            url = (
                f"https://newsapi.org/v2/everything"
                f"?q={city}+road+OR+traffic+OR+accident+OR+flood"
                f"&language=en&sortBy=publishedAt&pageSize=5"
                f"&apiKey={NEWS_API_KEY}"
            )
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, timeout=6.0)
                data = resp.json()

            for art in data.get("articles", [])[:5]:
                title = art.get("title", "")
                articles.append({
                    "title": title,
                    "url": art.get("url"),
                    "published_at": art.get("publishedAt"),
                    "sentiment": _news_sentiment(title),
                    "relevance": _relevance_score(title, city),
                    "source": art.get("source", {}).get("name", "NewsAPI"),
                })
            return articles
        except Exception:
            pass

    # --- Fallback: GNews (free tier, no API key required for basic query) ---
    try:
        query = f"{city} traffic road accident"
        url   = f"https://gnews.io/api/v4/search?q={query}&lang=en&max=5&token=free"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=6.0)
            data = resp.json()

        for art in data.get("articles", [])[:5]:
            title = art.get("title", "")
            articles.append({
                "title": title,
                "url": art.get("url"),
                "published_at": art.get("publishedAt"),
                "sentiment": _news_sentiment(title),
                "relevance": _relevance_score(title, city),
                "source": "GNews",
            })
    except Exception:
        pass

    return articles


# ---------------------------------------------------------------------------
# MODULE 4 — SOCIAL SIGNALS (Reddit RSS — no auth)
# ---------------------------------------------------------------------------

async def fetch_social_intel(city: str) -> list:
    """
    Scrapes public Reddit RSS feeds for real-time road hazard reports.
    Uses subreddits like r/india, r/bangalore, r/mumbai etc. (all public RSS).
    """
    city_subreddits = {
        "bangalore": "bangalore",
        "bengaluru": "bangalore",
        "mumbai": "mumbai",
        "delhi": "delhi",
        "hyderabad": "hyderabad",
        "chennai": "chennai",
        "pune": "pune",
        "kolkata": "kolkata",
    }

    city_low  = city.lower()
    subreddit = city_subreddits.get(city_low, "india")
    signals   = []

    try:
        # Reddit RSS — fully public, no auth
        url = f"https://www.reddit.com/r/{subreddit}/search.json?q=road+traffic+block+accident&sort=new&limit=5&t=day"
        async with httpx.AsyncClient(
            headers={"User-Agent": "NexusPath-Intel/1.0"},
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, timeout=6.0)
            data = resp.json()

        posts = data.get("data", {}).get("children", [])
        for post in posts[:5]:
            pd = post.get("data", {})
            title = pd.get("title", "")
            signals.append({
                "text": title,
                "source": f"Reddit r/{subreddit}",
                "url": f"https://reddit.com{pd.get('permalink', '')}",
                "score": pd.get("score", 0),
                "relevance": _relevance_score(title, city),
                "sentiment": _news_sentiment(title),
            })
    except Exception:
        pass

    return signals


# ---------------------------------------------------------------------------
# MAIN AGGREGATOR
# ---------------------------------------------------------------------------

async def gather_intel(
    lat: float,
    lon: float,
    dest_lat: Optional[float] = None,
    dest_lon: Optional[float] = None,
) -> dict:
    """
    Master function: runs all intelligence modules concurrently and
    returns a unified RiskIntelReport.
    """
    city = await _get_city_name(lat, lon)

    # Run all non-dependent fetches concurrently
    weather_task = fetch_weather_intel(lat, lon)
    news_task    = fetch_news_intel(city)
    social_task  = fetch_social_intel(city)
    traffic_task = (
        fetch_traffic_intel(lat, lon, dest_lat, dest_lon)
        if dest_lat is not None
        else asyncio.coroutine(lambda: {"available": False, "score": 0.0, "delay_min": 0})()
    )

    weather, news, social, traffic = await asyncio.gather(
        weather_task, news_task, social_task, traffic_task
    )

    # ── Composite risk score ──────────────────────────────────────────────
    # Weights: traffic 40% | weather 35% | news 15% | social 10%
    news_risk   = max((a["relevance"] for a in news   if a["sentiment"] == "negative"), default=0.0)
    social_risk = max((s["relevance"] for s in social if s["sentiment"] == "negative"), default=0.0)

    composite = round(
        traffic.get("score", 0.0) * 0.40
        + weather.get("score",  0.0) * 0.35
        + news_risk                  * 0.15
        + social_risk                * 0.10,
        3,
    )

    sources_fetched = []
    if weather.get("available"): sources_fetched.append("weather")
    if traffic.get("available"): sources_fetched.append("traffic")
    if news:                     sources_fetched.append("news")
    if social:                   sources_fetched.append("social")

    return {
        "location": {"lat": lat, "lon": lon, "city": city},
        "weather":  weather,
        "traffic":  traffic,
        "news":     news,
        "social":   social,
        "composite_risk_score": composite,
        "sources_fetched": sources_fetched,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
