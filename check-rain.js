// check-rain.js
// Checks tomorrow's forecast for your city and sends a Telegram message if rain is expected.
// Run once a day (e.g. via GitHub Actions cron).

// ---- CONFIG ----
// FOR LOCAL TESTING: paste your real values directly into the 4 lines below (inside the quotes).
// Before pushing to GitHub, change them back to empty strings "" so you don't commit real keys —
// the script will then automatically use GitHub Secrets (via environment variables) instead.
const LOCAL_OPENWEATHER_API_KEY = "";
const LOCAL_CITY_NAME = "";
const LOCAL_TELEGRAM_BOT_TOKEN = "";
const LOCAL_TELEGRAM_CHAT_ID = "";

const OPENWEATHER_API_KEY =
  LOCAL_OPENWEATHER_API_KEY || process.env.OPENWEATHER_API_KEY;
const CITY_NAME = LOCAL_CITY_NAME || process.env.CITY_NAME;
const TELEGRAM_BOT_TOKEN =
  LOCAL_TELEGRAM_BOT_TOKEN || process.env.TELEGRAM_BOT_TOKEN;
const TELEGRAM_CHAT_ID = LOCAL_TELEGRAM_CHAT_ID || process.env.TELEGRAM_CHAT_ID;

if (
  !OPENWEATHER_API_KEY ||
  !CITY_NAME ||
  !TELEGRAM_BOT_TOKEN ||
  !TELEGRAM_CHAT_ID
) {
  console.error(
    "Missing config. Fill in the LOCAL_ variables at the top of the file for local testing, " +
      "or set OPENWEATHER_API_KEY / CITY_NAME / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID as environment variables.",
  );
  process.exit(1);
}
// ----------------

const HOURS_TO_CHECK = 8; // look ahead this many hours for rain (roughly matches the gap between the 7am/1pm/7pm runs)

async function getForecast() {
  const url = `https://api.openweathermap.org/data/2.5/forecast?q=${encodeURIComponent(
    CITY_NAME,
  )}&appid=${OPENWEATHER_API_KEY}&units=metric`;

  const response = await fetch(url);

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(
      `OpenWeatherMap request failed (${response.status}): ${errorBody}`,
    );
  }

  return response.json();
}

function willItRain(forecastData) {
  // The free "5 day / 3 hour forecast" endpoint returns a list of 3-hour blocks.
  // We only look at blocks within the next HOURS_TO_CHECK hours.
  const cutoffCount = Math.ceil(HOURS_TO_CHECK / 3);
  const upcomingBlocks = forecastData.list.slice(0, cutoffCount);

  const rainBlocks = upcomingBlocks.filter((block) => {
    const weatherMain = block.weather?.[0]?.main?.toLowerCase() || "";
    const pop = block.pop || 0; // "probability of precipitation", 0 to 1
    return weatherMain.includes("rain") || pop >= 0.4;
  });

  if (rainBlocks.length === 0) {
    return { rainExpected: false };
  }

  // Find the highest chance of rain among the flagged blocks, for a nicer message
  const worstBlock = rainBlocks.reduce((worst, block) =>
    block.pop > worst.pop ? block : worst,
  );

  const time = new Date(worstBlock.dt * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return {
    rainExpected: true,
    chance: Math.round(worstBlock.pop * 100),
    time,
    description: worstBlock.weather?.[0]?.description || "rain",
  };
}

async function sendTelegramMessage(text) {
  const url = `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`;

  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: TELEGRAM_CHAT_ID,
      text,
    }),
  });

  if (!response.ok) {
    const errorBody = await response.text();
    throw new Error(
      `Telegram request failed (${response.status}): ${errorBody}`,
    );
  }

  return response.json();
}

async function main() {
  try {
    console.log(`Checking forecast for ${CITY_NAME}...`);
    const forecastData = await getForecast();
    const result = willItRain(forecastData);

    if (result.rainExpected) {
      const message = `🌧️ Rain expected today in ${CITY_NAME}!\nAround ${result.time}, ~${result.chance}% chance (${result.description}). Bring an umbrella!`;
      console.log(message);
      await sendTelegramMessage(message);
      console.log("Telegram message sent.");
    } else {
      console.log(
        "No rain expected in the next",
        HOURS_TO_CHECK,
        "hours. No message sent.",
      );
    }
  } catch (err) {
    console.error("Error running rain check:", err.message);
    process.exit(1);
  }
}

main();
