import json
import os
import time
from pathlib import Path

import requests


SYMBOLS = [
    "COPPERUSDT",
    "CLUSDT",
    "XAUUSDT",
    "XAGUSDT",
    "BTCUSDT",
    "ETHUSDT",
    "FILUSDT",
    "SOLUSDT",
    "ICPUSDT",
    "XRPUSDT",
    "DOGEUSDT",
    "SHIBUSDT",
    "DYDXUSDT",
    "HBARUSDT",
    "NOTUSDT",
    "APTUSDT",
    "ENAUSDT",
    "AEROUSDT",
    "CHZUSDT",
    "GALAUSDT",
    "SNXUSDT",
    "TRXUSDT",
    "POPCATUSDT",
    "PEPEUSDT",
    "LINKUSDT",
    "UNIUSDT",
    "ADAUSDT",
    "AVAXUSDT"
]


BASE = "https://fapi.binance.com"

STATE_FILE = Path("rsi-state.json")

RSI_LENGTH = 20

UPPER = 70.0
LOWER = 30.0


TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def calculate_rsi(closes):

    if len(closes) < RSI_LENGTH + 1:
        return None

    gain = 0.0
    loss = 0.0

    for i in range(1, RSI_LENGTH + 1):

        change = closes[i] - closes[i - 1]

        if change > 0:
            gain += change
        else:
            loss -= change

    gain /= RSI_LENGTH
    loss /= RSI_LENGTH

    for i in range(RSI_LENGTH + 1, len(closes)):

        change = closes[i] - closes[i - 1]

        current_gain = change if change > 0 else 0
        current_loss = -change if change < 0 else 0

        gain = (
            (RSI_LENGTH - 1) * gain +
            current_gain
        ) / RSI_LENGTH

        loss = (
            (RSI_LENGTH - 1) * loss +
            current_loss
        ) / RSI_LENGTH

    if loss == 0:
        return 100.0

    rs = gain / loss

    return 100.0 - (
        100.0 / (1.0 + rs)
    )


def load_state():

    if not STATE_FILE.exists():
        return {}

    try:

        return json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

    except Exception:

        return {}


def save_state(state):

    STATE_FILE.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def send_telegram(text):

    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_TOKEN}/sendMessage"
    )

    response = requests.post(
        url,
        json={
            "chat_id": CHAT_ID,
            "text": text
        },
        timeout=20
    )

    response.raise_for_status()


def main():

    session = requests.Session()

    exchange_info = session.get(
        BASE + "/fapi/v1/exchangeInfo",
        timeout=20
    )

    exchange_info.raise_for_status()

    available = {
        item["symbol"]
        for item in exchange_info.json()["symbols"]
    }

    state = load_state()

    changed = False

    for symbol in SYMBOLS:

        if symbol not in available:

            print(
                f"SKIP unavailable: {symbol}"
            )

            continue

        response = session.get(
            BASE + "/fapi/v1/klines",
            params={
                "symbol": symbol,
                "interval": "15m",
                "limit": 100
            },
            timeout=20
        )

        response.raise_for_status()

        rows = response.json()

        now_ms = int(
            time.time() * 1000
        )

        closed = [
            row
            for row in rows
            if len(row) >= 7
            and int(row[6]) <= now_ms
        ]

        if len(closed) < RSI_LENGTH + 2:

            print(
                f"SKIP insufficient: {symbol}"
            )

            continue

        closes = [
            float(row[4])
            for row in closed
        ]

        candle_times = [
            int(row[0])
            for row in closed
        ]

        previous_rsi = calculate_rsi(
            closes[:-1]
        )

        current_rsi = calculate_rsi(
            closes
        )

        if (
            previous_rsi is None
            or current_rsi is None
        ):
            continue

        direction = None

        if (
            previous_rsi <= UPPER
            and current_rsi > UPPER
        ):

            direction = "UP"

        elif (
            previous_rsi >= LOWER
            and current_rsi < LOWER
        ):

            direction = "DOWN"

        if not direction:
            continue

        candle_time = candle_times[-1]

        key = (
            f"{candle_time}:{direction}"
        )

        old_key = state.get(symbol)

        if key == old_key:
            continue

        if direction == "UP":

            text = (
                "🚨 Binance Futures\n"
                f"{symbol}\n"
                "RSI 20 از 70 عبور کرد\n"
                f"RSI: {current_rsi:.2f}\n"
                "تایم‌فریم: 15m"
            )

        else:

            text = (
                "🚨 Binance Futures\n"
                f"{symbol}\n"
                "RSI 20 از 30 پایین‌تر رفت\n"
                f"RSI: {current_rsi:.2f}\n"
                "تایم‌فریم: 15m"
            )

        print(text)

        send_telegram(text)

        state[symbol] = key

        changed = True

    if changed:

        save_state(state)


if __name__ == "__main__":
    main()
