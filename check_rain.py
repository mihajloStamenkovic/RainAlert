#!/usr/bin/env python3
# check_rain.py
# Checks today's forecast for your city and sends a Telegram message if rain is expected.
# Run a few times a day (e.g. via GitHub Actions cron).

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

# Windows consoles often default to a legacy codepage (e.g. cp1252) that can't
# encode the emoji in the rain message; force UTF-8 stdout/stderr so printing
# never crashes regardless of the terminal's default encoding.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8")

# ---- CONFIG ----
# FOR LOCAL TESTING: paste your real values directly into the 4 lines below (inside the quotes).
# Before pushing to GitHub, change them back to empty strings "" so you don't commit real keys —
# the script will then automatically use GitHub Secrets (via environment variables) instead.
LOCAL_OPENWEATHER_API_KEY = ""
LOCAL_CITY_NAME = ""
LOCAL_TELEGRAM_BOT_TOKEN = ""
LOCAL_TELEGRAM_CHAT_ID = ""

OPENWEATHER_API_KEY = LOCAL_OPENWEATHER_API_KEY or os.environ.get("OPENWEATHER_API_KEY")
CITY_NAME = LOCAL_CITY_NAME or os.environ.get("CITY_NAME")
TELEGRAM_BOT_TOKEN = LOCAL_TELEGRAM_BOT_TOKEN or os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = LOCAL_TELEGRAM_CHAT_ID or os.environ.get("TELEGRAM_CHAT_ID")

if not all([OPENWEATHER_API_KEY, CITY_NAME, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    print(
        "Missing config. Fill in the LOCAL_ variables at the top of the file for local testing, "
        "or set OPENWEATHER_API_KEY / CITY_NAME / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID as environment variables.",
        file=sys.stderr,
    )
    sys.exit(1)
# ----------------

HOURS_TO_CHECK = 8  # look ahead this many hours for rain (roughly matches the gap between the 7am/1pm/7pm runs)


def get_forecast():
    query = urllib.parse.urlencode(
        {"q": CITY_NAME, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    )
    url = f"https://api.openweathermap.org/data/2.5/forecast?{query}"

    try:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"OpenWeatherMap request failed ({e.code}): {error_body}")


def will_it_rain(forecast_data):
    # The free "5 day / 3 hour forecast" endpoint returns a list of 3-hour blocks.
    # We only look at blocks within the next HOURS_TO_CHECK hours.
    cutoff_count = -(-HOURS_TO_CHECK // 3)  # ceil division
    upcoming_blocks = forecast_data["list"][:cutoff_count]

    rain_blocks = []
    for block in upcoming_blocks:
        weather = block.get("weather") or [{}]
        weather_main = (weather[0].get("main") or "").lower()
        pop = block.get("pop", 0)  # "probability of precipitation", 0 to 1
        if "rain" in weather_main or pop >= 0.4:
            rain_blocks.append(block)

    if not rain_blocks:
        return {"rain_expected": False}

    # Find the highest chance of rain among the flagged blocks, for a nicer message
    worst_block = max(rain_blocks, key=lambda b: b.get("pop", 0))

    time_str = datetime.fromtimestamp(worst_block["dt"]).strftime("%I:%M %p")

    weather = worst_block.get("weather") or [{}]
    return {
        "rain_expected": True,
        "chance": round(worst_block.get("pop", 0) * 100),
        "time": time_str,
        "description": weather[0].get("description", "rain"),
    }


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": text}).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        raise RuntimeError(f"Telegram request failed ({e.code}): {error_body}")


def main():
    try:
        print(f"Checking forecast for {CITY_NAME}...")
        forecast_data = get_forecast()
        result = will_it_rain(forecast_data)

        if result["rain_expected"]:
            message = (
                f"🌧️ Rain expected today in {CITY_NAME}!\n"
                f"Around {result['time']}, ~{result['chance']}% chance ({result['description']}). "
                "Bring an umbrella!"
            )
            print(message)
            send_telegram_message(message)
            print("Telegram message sent.")
        else:
            print(f"No rain expected in the next {HOURS_TO_CHECK} hours. No message sent.")
    except Exception as err:
        print(f"Error running rain check: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
