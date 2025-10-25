import datetime
import yfinance as yf
import pandas as pd
import subprocess
import shlex
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from prophet import Prophet

analyzer = SentimentIntensityAnalyzer()

class PriceAgent:
    """Fetch recent price history for tickers."""
    def fetch(self, ticker, period='7d', interval='1d'):
        df = yf.download(ticker, period=period, interval=interval, progress=False)
        if df.empty:
            return None
        df = df.reset_index()[['Date','Close']].rename(columns={'Date':'ds','Close':'y'})
        return df

class SentimentAgent:
    """Scrape X/Twitter using snscrape (if available) and score sentiment with VADER."""
    def scrape(self, query, max_tweets=200):
        # Use snscrape's python API via subprocess to keep dependency simple and avoid API keys
        try:
            cmd = f"snscrape --jsonl --max {max_tweets} twitter-search '{query}'"
            parts = shlex.split(cmd)
            p = subprocess.run(parts, capture_output=True, text=True, check=True)
            tweets = [l for l in p.stdout.splitlines() if l.strip()]
            texts = []
            for line in tweets:
                try:
                    import json
                    obj = json.loads(line)
                    texts.append(obj.get('content',''))
                except Exception:
                    continue
        except Exception:
            # as a fallback return empty list
            texts = []

        scores = [analyzer.polarity_scores(t)['compound'] for t in texts if t]
        if not scores:
            return {'count':0, 'avg':0.0, 'scores':[]}
        return {'count':len(scores), 'avg':float(sum(scores)/len(scores)), 'scores':scores}

class ForecastAgent:
    """Produce a short-term forecast using Prophet."""
    def forecast(self, df, periods=3):
        if df is None or df.empty:
            return None
        m = Prophet()
        m.fit(df)
        future = m.make_future_dataframe(periods=periods)
        fcst = m.predict(future)
        # Return only the forecast for the horizon
        return fcst[['ds','yhat','yhat_lower','yhat_upper']].tail(periods)

class SynthesizerAgent:
    """Meta-agent: combine outputs into a report string and simple risk flags."""
    def synthesize(self, ticker, price_df, sentiment, forecast_df):
        lines = []
        lines.append(f"Report for {ticker} - {datetime.date.today().isoformat()}")
        if price_df is not None and not price_df.empty:
            last = price_df.iloc[-1]['y']
            lines.append(f"Last close: {last:.2f}")
        if sentiment and sentiment['count']>0:
            lines.append(f"Social sentiment (avg): {sentiment['avg']:.3f} from {sentiment['count']} posts")
            if sentiment['avg']>0.6:
                lines.append("Hype risk: HIGH (very positive social buzz)")
        if forecast_df is not None and not forecast_df.empty:
            next_hat = forecast_df.iloc[ -1 ]['yhat']
            lines.append(f"Forecast {len(forecast_df)} days out: {next_hat:.2f}")
        return "\n".join(lines)
