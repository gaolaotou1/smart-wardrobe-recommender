from dataclasses import asdict, dataclass

import httpx


@dataclass(frozen=True)
class WeatherEvidence:
    location: str
    observed_at: str
    temperature_c: float
    apparent_temperature_c: float
    precipitation_mm: float
    wind_speed_kmh: float
    weather_code: int

    @property
    def suggested_season(self):
        if self.apparent_temperature_c <= 12:
            return "winter"
        if self.apparent_temperature_c >= 25:
            return "summer"
        return "spring_and_autumn"

    def to_dict(self):
        return {**asdict(self), "suggested_season": self.suggested_season}


class OpenMeteoWeatherPort:
    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
    forecast_url = "https://api.open-meteo.com/v1/forecast"

    async def current(self, location: str) -> WeatherEvidence:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            geocoding = await client.get(
                self.geocoding_url,
                params={"name": location, "count": 1, "language": "zh", "format": "json"},
            )
            geocoding.raise_for_status()
            places = geocoding.json().get("results", [])
            if not places:
                raise ValueError("没有找到该城市")
            place = places[0]
            forecast = await client.get(
                self.forecast_url,
                params={
                    "latitude": place["latitude"],
                    "longitude": place["longitude"],
                    "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
                    "timezone": "Asia/Shanghai",
                },
            )
            forecast.raise_for_status()
        current = forecast.json()["current"]
        return WeatherEvidence(
            location=place.get("name") or location,
            observed_at=current["time"],
            temperature_c=float(current["temperature_2m"]),
            apparent_temperature_c=float(current["apparent_temperature"]),
            precipitation_mm=float(current["precipitation"]),
            wind_speed_kmh=float(current["wind_speed_10m"]),
            weather_code=int(current["weather_code"]),
        )
