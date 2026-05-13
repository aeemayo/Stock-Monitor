# Stock Sentinel — AI-Driven Stock Sentiment Analysis & Forecasting

A multi-tenant Flask web application with user authentication that monitors stock portfolios, analyzes Farcaster sentiment via the Neynar API, forecasts price movements with Prophet, and delivers AI-synthesized alerts through a premium dark-mode dashboard.

## How It Works

### 1. **User Authentication**
- Register and sign in with username/email and password
- Passwords are hashed with bcrypt (never stored in plaintext)
- Session-based authentication via Flask-Login
- All data is scoped per-user — full multi-tenant isolation

### 2. **Portfolio Management**
- Create multiple stock portfolios via the web dashboard
- Add stock holdings (ticker symbols and share counts) to each portfolio
- View, edit, and delete portfolios and holdings through the UI

### 3. **Automated Analysis Workflow** (runs on a schedule)
The app runs a background job that automatically:

- **Price Fetching**: Downloads 14 days of historical stock data using `yfinance`
- **Sentiment Analysis**: Searches Farcaster casts about each stock using the Neynar API and analyzes sentiment
- **Forecasting**: Uses `Prophet` time-series forecasting to predict next 3 days of price movements
- **AI Synthesis**: Multi-agent system processes all data and generates a comprehensive analysis report

### 4. **Alert Generation & Delivery**
- AI agents synthesize all data into actionable insights
- Alerts are stored in the database with timestamps
- Filter alerts by portfolio, date range
- Dismiss individual alerts

### 5. **Web Dashboard**
- Premium dark-mode UI built with Tailwind CSS and glassmorphism design
- **Portfolios Page**: View all portfolios, statistics, and quick-create widget
- **Portfolio Detail**: See holdings table, add new tickers, manage positions
- **Alerts History**: Filterable alert table with portfolio and date filters
- **Analytics**: Portfolio distribution charts, holdings by sector, and price forecast visualizations
- **Settings**: User profile and preferences
- **Support**: FAQ and contact form

## Technology Stack

| Component | Technology |
|-----------|-----------|
| **Web Server** | Flask + Jinja2 templates |
| **Authentication** | Flask-Login + bcrypt |
| **Database** | PostgreSQL (psycopg2) |
| **Frontend** | Tailwind CSS (CDN), Google Material Symbols |
| **Scheduling** | APScheduler (background jobs) |
| **Stock Data** | yfinance |
| **Sentiment** | Farcaster casts (Neynar API) + VADER sentiment analysis |
| **Forecasting** | Facebook Prophet |
| **AI Analysis** | ROMA multi-agent framework |

## Getting Started

1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables (database URL, etc.)
3. Run the app: `python app.py`
4. Register a new account at `http://localhost:5000/register`

## Architecture Overview

### Backend Stack
- **Flask**: Web server and REST API endpoints
- **Flask-Login + bcrypt**: Session-based authentication with password hashing
- **PostgreSQL (psycopg2)**: Data persistence layer (users, portfolios, holdings, alerts)
- **APScheduler**: Scheduled background jobs that run the ROMA workflow at market close
- **ROMA Agents**: Multi-agent AI framework for price analysis, sentiment analysis, forecasting, and synthesis
- **yfinance**: Stock price data fetching
- **Neynar API**: Farcaster sentiment search
- **Prophet**: Time-series forecasting

---

## Frontend Architecture

The **frontend** is a server-rendered web application built with **Flask**, **Jinja2 templates**, and **Tailwind CSS** (dark mode). It features a persistent sidebar, glassmorphism card design, and Google Material Symbols icons.

### Core Pages

| Route | Template | Description |
|-------|----------|-------------|
| `/register` | `register.html` | Account creation (standalone, no sidebar) |
| `/login` | `login.html` | Sign in (standalone, no sidebar) |
| `/dashboard` | `dashboard.html` | Portfolio list, stats, quick-create form |
| `/portfolio/<id>` | `portfolio.html` | Holdings table, add holding widget, stats |
| `/alerts` | `alerts.html` | Filterable alerts table with empty state |
| `/analytics` | `analytics.html` | Charts: donut, bar, line, forecast |
| `/settings` | `settings.html` | User profile, preferences, integrations |
| `/support` | `support.html` | FAQ and contact form |

All authenticated pages extend `base.html`, which contains the sidebar navigation and flash message area.


---

## Authentication Flow

The app uses **Flask-Login** for session management and **bcrypt** for password hashing.

```
User visits any protected route
    ↓
Flask-Login checks session cookie
    ↓
If no session → redirect to /login
    ↓
User signs in (username/email + password)
    ↓
bcrypt.checkpw() verifies password against stored hash
    ↓
login_user() creates session → redirect to /dashboard
    ↓
All queries scoped by current_user.id (multi-tenant isolation)
```

### Backend APIs

The frontend makes **server-side** requests (no JavaScript/AJAX). All data retrieval happens on the server before the HTML is rendered.

#### Connection Management
- **`db.get_db_connection()`**: Returns a raw psycopg2 connection from the connection pool
- Called by each Flask route to query the database using `RealDictCursor`
- Automatically handles connection pooling and thread safety

#### Database Schema (PostgreSQL)
We use raw SQL tables (no ORM). Data is returned as Python dictionaries.
```sql
users
  ├─ id (SERIAL, primary key)
  ├─ username (VARCHAR, unique)
  ├─ email (VARCHAR, unique)
  ├─ password_hash (VARCHAR)  ← bcrypt hash
  └─ created_at (TIMESTAMP)

portfolios
  ├─ id (SERIAL, primary key)
  ├─ user_id (Foreign Key → users.id)
  └─ name (VARCHAR)

holdings
  ├─ id (SERIAL, primary key)
  ├─ portfolio_id (Foreign Key → portfolios.id)
  ├─ ticker (VARCHAR)
  └─ shares (FLOAT)

alerts
  ├─ id (SERIAL, primary key)
  ├─ portfolio_id (Foreign Key → portfolios.id)
  ├─ message (TEXT) ← Contains synthesis results
  └─ created_at (TIMESTAMP)
```

---

## Completed Features

- [x] User registration and login (Flask-Login + bcrypt)
- [x] Multi-tenant data isolation (all queries scoped by user_id)
- [x] Portfolio CRUD (create, view, delete)
- [x] Holdings CRUD (add ticker/shares, view, delete)
- [x] Alert filtering by portfolio and date range
- [x] Alert dismissal
- [x] Tailwind CSS dark-mode UI with glassmorphism design
- [x] Responsive sidebar navigation with mobile header
- [x] Analytics page with SVG charts
- [x] Settings and Support pages
- [x] Farcaster sentiment analysis via Neynar API
- [x] Prophet time-series forecasting
- [x] PostgreSQL with connection pooling (psycopg2)

## Remaining Enhancements

- [ ] Real-time alerts using WebSockets
- [ ] Portfolio edit form (name/description)
- [ ] Holding edit form (update shares)
- [ ] Dynamic chart data (replace static SVG mockups with real data)
- [ ] Password reset / email verification
- [ ] Role-based access control

---

## Quick Start

1. Create a Python environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # on Windows use: .venv\Scripts\activate
pip install -r requirements.txt
```

2. Start a PostgreSQL database using Docker:

```bash
docker run --name stocks-postgres \
  -e POSTGRES_USER=aeem \
  -e POSTGRES_PASSWORD=bunymide \
  -e POSTGRES_DB=stocks_db \
  -p 5432:5432 -d postgres
```

3. Copy the example env file and configure:

```bash
cp .env.example .env
# Set DATABASE_URL=postgresql://aeem:bunymide@localhost:5432/stocks_db
# Set NEYNAR_API_KEY=your_key_here
# Set SECRET_KEY=a-strong-random-string
```

4. Run the app:

```bash
python app.py
```

5. Open `http://localhost:5000/register` to create your first account and start using the dashboard.

The APScheduler job will run in-process and trigger the ROMA workflow near market close (configured in `.env`).

## Notes
- Set a strong `SECRET_KEY` in production — it secures session cookies.
- The sentiment agents use the Neynar API (requires `NEYNAR_API_KEY` in `.env`).
- The forecasting agent uses `prophet` by default; if installation is problematic you can swap to a lightweight sklearn regressor.

Installing ROMA (optional)

ROMA (Recursive Open Meta-Agent) is an optional multi-agent framework you mentioned. Because ROMA's distribution source/name can vary, it is not pinned in `requirements.txt`. To enable ROMA integration in this project, install ROMA manually. Examples (replace with the correct repo or package name):

```bash
# If ROMA is on PyPI (replace with the real package name):
pip install roma

# Or install directly from a GitHub repo (replace <org>/<repo> and branch/tag as needed):
pip install git+https://github.com/<org>/<repo>.git@main#egg=roma
```

After installing ROMA, restart the Flask app. The codebase will detect ROMA at runtime and use it if the package exposes a compatible `run_workflow` entrypoint. If ROMA isn't installed, the scaffold falls back to the built-in ROMA-like workflow implementation.
