# AI-Driven Stock Sentinel (Scaffold)

This repository is a starter scaffold for the AI-Driven Stock Sentinel you described: a Flask+ROMA setup that fetches prices, scrapes X/Twitter sentiment, runs short-term forecasts, synthesizes results, stores portfolios in SQLite, and sends alerts via Slack/Email.

## Architecture Overview

### Backend Stack
- **Flask**: Web server and REST API endpoints
- **SQLAlchemy + SQLite**: Data persistence layer (portfolios, holdings, alerts)
- **APScheduler**: Scheduled background jobs that run the ROMA workflow at market close
- **ROMA Agents**: Multi-agent AI framework for price analysis, sentiment analysis, forecasting, and synthesis
- **yfinance**: Stock price data fetching
- **snscrape**: Twitter/X sentiment scraping
- **Prophet**: Time-series forecasting
- **Slack/Email**: Alert notifications

---

## Frontend Scope & Architecture

The **frontend** is a lightweight server-rendered web application built with **Flask** and **Jinja2 templates**. It provides users with a clean, simple interface to view portfolios and alerts.

### Core Frontend Pages

#### 1. Dashboard Page (`/dashboard`)
**Endpoint**: `GET /dashboard` (default route)

**Functionality**:
- Displays all user portfolios in a list
- Shows portfolio name and ID
- Link to navigate to alerts view
- Starting point for monitoring

**Current Template**: `templates/dashboard.html`

**Data Flow**:
```
User visits /dashboard
    ↓
Flask route calls get_session()
    ↓
Query database: SELECT id, name FROM portfolios
    ↓
Render dashboard.html with portfolios list
    ↓
HTML displayed in browser
```

#### 2. Alerts Page (`/alerts`)
**Endpoint**: `GET /alerts`

**Functionality**:
- Displays the most recent 50 alerts
- Shows alert metadata:
  - Alert timestamp (created_at)
  - Associated portfolio ID
  - Alert message (contains synthesis results from ROMA workflow)
- Link to return to dashboard

**Current Template**: `templates/alerts.html`

**Data Flow**:
```
User visits /alerts
    ↓
Flask route calls get_session()
    ↓
Query database: SELECT id, portfolio_id, message, created_at FROM alerts 
                ORDER BY created_at DESC LIMIT 50
    ↓
Render alerts.html with alerts list
    ↓
HTML displayed in browser
```

---

## Backend-to-Frontend Integration

### How Data Flows from Backend to Frontend

#### 1. **User Navigation**
```
Browser Request (GET /dashboard)
    ↓
Flask app.py routes request to dashboard() function
    ↓
Function calls get_session() from db.py
    ↓
SQLAlchemy retrieves data from SQLite
    ↓
Jinja2 template renders data as HTML
    ↓
HTML response sent to browser
```

#### 2. **Data Source Chain**
```
ROMA Workflow (scheduler.py)
    ↓
Runs at configured market close time (e.g., 4:30 PM on weekdays)
    ↓
Agents analyze prices, sentiment, forecasts
    ↓
SynthesizerAgent generates alert message
    ↓
Alert saved to database: models.Alert
    ↓
Frontend displays on /alerts page
```

### Backend APIs (Currently Used by Frontend)

The frontend currently makes **server-side** requests (no JavaScript/AJAX). All data retrieval happens on the server before the HTML is rendered.

#### Session Management
- **`db.get_session()`**: Returns a SQLAlchemy session
- Called by each Flask route to query the database
- Automatically handles connection pooling and thread safety

#### Database Models (orm.py)
```python
Portfolio
  ├─ id (Integer, primary key)
  └─ name (String)

Holding
  ├─ id (Integer, primary key)
  ├─ portfolio_id (Foreign Key → Portfolio.id)
  ├─ ticker (String)
  └─ shares (Float)

Alert
  ├─ id (Integer, primary key)
  ├─ portfolio_id (Foreign Key → Portfolio.id)
  ├─ message (Text) ← Contains synthesis results
  └─ created_at (DateTime)
```

---

## Current Frontend Limitations (Scaffold Phase)

1. **No Portfolio Management UI**
   - Users cannot create portfolios through the web interface
   - Must use database tools or API calls to add portfolios
   - No way to edit portfolio names

2. **No Holdings Management**
   - Cannot add stocks to a portfolio from the frontend
   - No UI to view holdings by portfolio

3. **Read-Only Interface**
   - All pages are display-only (GET requests only)
   - No forms (POST/PUT/DELETE requests)

4. **Basic Styling**
   - Minimal CSS
   - No responsive design framework
   - Not mobile-friendly

5. **No Real-Time Updates**
   - Must manually refresh pages to see new alerts
   - No WebSocket or polling for live updates

6. **Limited Filtering & Search**
   - Cannot filter alerts by portfolio
   - Cannot search or sort alerts

---

## Recommended Frontend Enhancements

### Phase 1: Basic CRUD Operations
- [ ] Add form to create new portfolios
- [ ] Add form to add holdings to portfolios
- [ ] Add ability to delete portfolios/holdings
- [ ] Basic form validation on the frontend

### Phase 2: Improved UX
- [ ] Add CSS framework (Bootstrap/Tailwind)
- [ ] Make layout responsive and mobile-friendly
- [ ] Add navigation header with branding
- [ ] Add breadcrumb navigation

### Phase 3: Advanced Features
- [ ] Real-time alerts using WebSockets
- [ ] Alert filtering by portfolio, date range
- [ ] Portfolio performance dashboard with metrics
- [ ] Charts showing price history and forecasts
- [ ] Alert dismissal/archiving
- [ ] Dark mode toggle
- [ ] User authentication (if multi-user)

### Phase 4: Interactivity
- [ ] Client-side form validation using JavaScript
- [ ] Auto-refresh alerts every N seconds
- [ ] Modal dialogs for confirmations
- [ ] Loading spinners and error messages
- [ ] Search functionality with autocomplete

---

### Technology Stack for Frontend Enhancements
- **HTML/CSS/JavaScript**: Core frontend (already in use)
- **Bootstrap or Tailwind CSS**: Responsive styling
- **HTMX or Alpine.js**: Lightweight interactivity without build tools
- **Chart.js or Plotly.js**: Data visualization
- **Socket.io**: Real-time updates (optional)

---

Quick start

1. Create a Python environment and install dependencies:

```bash
python -m venv .venv
source .venv/Scripts/activate   # on Windows use: .venv\\Scripts\\activate
pip install -r requirements.txt
```

2. Copy the example env file and edit secrets:

```bash
cp .env.example .env
# edit .env and fill SLACK_WEBHOOK_URL, SMTP_* etc.
```

3. Run the Flask app:

```bash
flask run --host=0.0.0.0 --port=5000
```

The APScheduler job will run in-process and trigger the ROMA workflow near market close (configured in `.env`).

Notes & next steps
- This is a scaffold. You should add API keys and test scraping on your machine.
- The sentiment scrapers use `snscrape` (no Twitter API key required) as a starting point.
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
