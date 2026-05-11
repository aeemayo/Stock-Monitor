from .agents import PriceAgent, SentimentAgent, ForecastAgent, SynthesizerAgent
from db import get_db_connection, put_db_connection
import os
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from . import ROMA_AVAILABLE, roma_framework

load_dotenv()

price_agent = PriceAgent()
sent_agent = SentimentAgent()
forecast_agent = ForecastAgent()
synth = SynthesizerAgent()

def run_root_workflow(portfolio_id=None):
    """Root runner: if an external ROMA framework is installed and exposes a
    `run_workflow` callable, delegate the work to it. Otherwise, run the
    local/fallback implementation (the previous behavior).
    """
    # If a ROMA framework is installed and exposes a run_workflow entrypoint,
    # delegate to it. This avoids hardcoding ROMA internals here and keeps the
    # scaffold non-breaking when ROMA isn't available.
    if ROMA_AVAILABLE and roma_framework is not None:
        if hasattr(roma_framework, 'run_workflow'):
            try:
                return roma_framework.run_workflow(portfolio_id=portfolio_id)
            except Exception as e:
                print('ROMA run_workflow failed; falling back to local workflow:', e)

    # Local fallback implementation
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if portfolio_id:
                cur.execute("SELECT * FROM holdings WHERE portfolio_id = %s", (portfolio_id,))
            else:
                cur.execute("SELECT * FROM holdings")
            holdings = cur.fetchall()

            for h in holdings:
                ticker = h['ticker']
                price_df = price_agent.fetch(ticker, period='14d')
                sentiment = sent_agent.scrape(ticker)  # searches for the ticker symbol/term
                forecast = forecast_agent.forecast(price_df, periods=3)
                report = synth.synthesize(ticker, price_df, sentiment, forecast)
                
                # store alert
                cur.execute(
                    "INSERT INTO alerts (portfolio_id, message) VALUES (%s, %s)",
                    (h['portfolio_id'], report)
                )
                conn.commit()
                
    except Exception as e:
        conn.rollback()
        print(f"Workflow error: {e}")
    finally:
        put_db_connection(conn)

    return True
