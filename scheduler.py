from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import os
from dotenv import load_dotenv
from roma.workflow import run_root_workflow

load_dotenv()

MARKET_HOUR = int(os.getenv('MARKET_CLOSE_HOUR', '16'))
MARKET_MIN = int(os.getenv('MARKET_CLOSE_MINUTE', '30'))

_scheduler = None

def _job():
    # This runs at market close and triggers the ROMA workflow
    print(f"[Scheduler] Running ROMA workflow at {datetime.now()}")
    try:
        run_root_workflow()
    except Exception as e:
        print('Error running workflow:', e)


def start_scheduler(app=None):
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    # Run every weekday at configured market close time
    trigger = CronTrigger(day_of_week='mon-fri', hour=MARKET_HOUR, minute=MARKET_MIN)
    scheduler.add_job(_job, trigger, id='daily_roma')
    scheduler.start()
    _scheduler = scheduler
    print(f"Scheduler started: daily ROMA job at {MARKET_HOUR}:{MARKET_MIN}")
    return scheduler
