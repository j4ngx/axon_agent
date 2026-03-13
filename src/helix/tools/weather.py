"""Open-Meteo weather utility.

Fetches current weather data from the free Open-Meteo API.
This is NOT a Tool — it's a helper used by DailyBriefingTool.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes → human descriptions
_WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def weather_code_to_description(code: int) -> str:
    """Translate a WMO weather code to a human-readable description."""
    return _WMO_CODES.get(code, f"Unknown ({code})")


async def fetch_weather(
    lat: float,
    lon: float,
    http_client: httpx.AsyncClient | None = None,
) -> dict:
    """Fetch current weather from Open-Meteo.

    Args:
        lat: Latitude.
        lon: Longitude.
        http_client: Optional shared httpx client. A temporary one is
            created if not provided.

    Returns:
        A dict with keys: ``temperature``, ``wind_speed``,
        ``humidity``, ``description``, ``raw``.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "current_weather": "true",
        "hourly": "relative_humidity_2m",
        "forecast_days": 1,
    }

    close_after = False
    if http_client is None:
        http_client = httpx.AsyncClient(timeout=15.0)
        close_after = True

    try:
        response = await http_client.get(_BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        logger.error("Open-Meteo request failed", extra={"error": str(exc)})
        return {"error": str(exc)}
    finally:
        if close_after:
            await http_client.aclose()

    current = data.get("current_weather", {})
    hourly = data.get("hourly", {})
    humidity_values = hourly.get("relative_humidity_2m", [])
    current_humidity = humidity_values[0] if humidity_values else None

    return {
        "temperature": current.get("temperature"),
        "wind_speed": current.get("windspeed"),
        "humidity": current_humidity,
        "description": weather_code_to_description(current.get("weathercode", -1)),
        "raw": current,
    }
