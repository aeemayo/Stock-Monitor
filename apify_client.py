import os
import requests

APIFY_TOKEN = os.getenv("APIFY_TOKEN")
APIFY_ACTOR_ID = os.getenv("APIFY_ACTOR_ID", "canadesk~yahoo-finance")
TIMEOUT = 30


def fetch_prices(tickers: list[str]) -> dict[str, float | None]:
    """
    Call Apify run-sync endpoint; returns {ticker: price} for each requested
    ticker. Price is None on any failure (network, actor error, missing field).
    """
    if not APIFY_TOKEN or not tickers:
        return {t: None for t in tickers}

    url = (
        f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}"
        f"https://api.apify.com/v2/acts/canadesk~yahoo-finance/run-sync-get-dataset-items"
        f"?token={APIFY_TOKEN}&timeout={TIMEOUT}&memory=128"
    )
    payload = {"tickers": tickers, "type": "STOCKS", "proxy": {"useApifyProxy": True}}

    try:
        response = requests.post(url, json=payload, timeout=TIMEOUT + 5)
        response.raise_for_status()
        items = response.json()
    except Exception as exc:
        print(f"[Apify] fetch_prices error: {exc}")
        return {t: None for t in tickers}

    result = {t: None for t in tickers}
    for item in items:
        symbol = (item.get("ticker") or item.get("symbol") or "").upper()
        price = item.get("regularMarketPrice") or item.get("currentPrice")
        if symbol and symbol in result and price is not None:
            result[symbol] = float(price)

    return result


def fetch_price(ticker: str) -> float | None:
    return fetch_prices([ticker]).get(ticker)
