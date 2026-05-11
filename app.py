import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from db import init_db, get_db_connection, put_db_connection
from psycopg2.extras import RealDictCursor
from scheduler import start_scheduler
from roma.workflow import run_root_workflow

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://localhost/stocks')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize on startup
def initialize_app():
    init_db(app.config['DATABASE_URL'])
    # Don't start scheduler on serverless
    if os.getenv('ENVIRONMENT') != 'vercel':
        start_scheduler(app)

# ================== DASHBOARD ROUTES ==================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Display all portfolios and create portfolio form"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolios ORDER BY id")
            portfolios = cur.fetchall()
            
            for portfolio in portfolios:
                cur.execute("SELECT * FROM holdings WHERE portfolio_id = %s", (portfolio['id'],))
                portfolio['holdings'] = cur.fetchall()
            
            cur.execute("SELECT COUNT(*) as count FROM holdings")
            row = cur.fetchone()
            total_holdings = row['count'] if row else 0
    finally:
        put_db_connection(conn)
        
    return render_template('dashboard.html', 
                         portfolios=portfolios,
                         total_holdings=total_holdings)

# ================== PORTFOLIO ROUTES ==================

@app.route('/portfolio/create', methods=['POST'])
def create_portfolio():
    """Create a new portfolio"""
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        flash('Portfolio name is required', 'error')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO portfolios (name, description) VALUES (%s, %s)", (name, description))
        conn.commit()
        
        flash(f'Portfolio "{name}" created successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error creating portfolio: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    return redirect(url_for('dashboard'))

@app.route('/portfolio/<int:portfolio_id>')
def view_portfolio(portfolio_id):
    """View portfolio details and holdings"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolios WHERE id = %s", (portfolio_id,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                flash('Portfolio not found', 'error')
                return redirect(url_for('dashboard'))
            
            cur.execute("SELECT * FROM holdings WHERE portfolio_id = %s", (portfolio_id,))
            holdings = cur.fetchall()
            
            total_shares = sum(h['shares'] for h in holdings)
            unique_tickers = len(set(h['ticker'] for h in holdings))
            
            # Get recent alerts for this portfolio
            cur.execute("SELECT COUNT(*) as count FROM alerts WHERE portfolio_id = %s", (portfolio_id,))
            row = cur.fetchone()
            recent_alerts = row['count'] if row else 0
            
    finally:
        put_db_connection(conn)
        
    return render_template('portfolio.html',
                         portfolio=portfolio,
                         holdings=holdings,
                         total_shares=total_shares,
                         unique_tickers=unique_tickers,
                         recent_alerts=recent_alerts)

@app.route('/portfolio/<int:portfolio_id>/delete', methods=['POST'])
def delete_portfolio(portfolio_id):
    """Delete a portfolio and all associated holdings and alerts"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT name FROM portfolios WHERE id = %s", (portfolio_id,))
            portfolio = cur.fetchone()
            
            if not portfolio:
                flash('Portfolio not found', 'error')
                return redirect(url_for('dashboard'))
            
            portfolio_name = portfolio['name']
            
            cur.execute("DELETE FROM holdings WHERE portfolio_id = %s", (portfolio_id,))
            cur.execute("DELETE FROM alerts WHERE portfolio_id = %s", (portfolio_id,))
            cur.execute("DELETE FROM portfolios WHERE id = %s", (portfolio_id,))
            
        conn.commit()
        flash(f'Portfolio "{portfolio_name}" deleted successfully', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting portfolio: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    return redirect(url_for('dashboard'))

@app.route('/portfolio/<int:portfolio_id>/edit')
def edit_portfolio(portfolio_id):
    """Edit portfolio form (placeholder)"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM portfolios WHERE id = %s", (portfolio_id,))
            if not cur.fetchone():
                flash('Portfolio not found', 'error')
                return redirect(url_for('dashboard'))
    finally:
        put_db_connection(conn)
    
    # TODO: Create edit template
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

# ================== HOLDINGS ROUTES ==================

@app.route('/portfolio/<int:portfolio_id>/holding/create', methods=['POST'])
def create_holding(portfolio_id):
    """Add a holding to a portfolio"""
    ticker = request.form.get('ticker', '').strip().upper()
    shares = request.form.get('shares', '')
    
    if not ticker or not shares:
        flash('Ticker and shares are required', 'error')
        return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))
    
    try:
        shares = float(shares)
        if shares <= 0:
            raise ValueError("Shares must be positive")
    except ValueError as e:
        flash(f'Invalid shares value: {str(e)}', 'error')
        return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM portfolios WHERE id = %s", (portfolio_id,))
            if not cur.fetchone():
                flash('Portfolio not found', 'error')
                return redirect(url_for('dashboard'))
            
            cur.execute("INSERT INTO holdings (portfolio_id, ticker, shares) VALUES (%s, %s, %s)", 
                        (portfolio_id, ticker, shares))
            
        conn.commit()
        flash(f'Added {shares} shares of {ticker} to portfolio', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error adding holding: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

@app.route('/holding/<int:holding_id>/delete', methods=['POST'])
def delete_holding(holding_id):
    """Delete a holding from a portfolio"""
    conn = get_db_connection()
    portfolio_id = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT portfolio_id, ticker FROM holdings WHERE id = %s", (holding_id,))
            holding = cur.fetchone()
            
            if not holding:
                flash('Holding not found', 'error')
                return redirect(url_for('dashboard'))
            
            portfolio_id = holding['portfolio_id']
            ticker = holding['ticker']
            
            cur.execute("DELETE FROM holdings WHERE id = %s", (holding_id,))
            
        conn.commit()
        flash(f'Removed {ticker} from portfolio', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting holding: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    if portfolio_id:
        return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))
    return redirect(url_for('dashboard'))

@app.route('/holding/<int:holding_id>/edit')
def edit_holding(holding_id):
    """Edit holding form (placeholder)"""
    conn = get_db_connection()
    portfolio_id = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT portfolio_id FROM holdings WHERE id = %s", (holding_id,))
            holding = cur.fetchone()
            
            if not holding:
                flash('Holding not found', 'error')
                return redirect(url_for('dashboard'))
                
            portfolio_id = holding['portfolio_id']
    finally:
        put_db_connection(conn)
    
    # TODO: Create edit template
    if portfolio_id:
        return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))
    return redirect(url_for('dashboard'))

# ================== ALERTS ROUTES ==================

@app.route('/alerts')
def alerts():
    """Display alerts with filtering options"""
    portfolio_id = request.args.get('portfolio_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = "SELECT * FROM alerts WHERE 1=1"
            params = []
            
            if portfolio_id:
                query += " AND portfolio_id = %s"
                params.append(portfolio_id)
            
            if date_from:
                try:
                    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                    query += " AND created_at >= %s"
                    params.append(date_from_obj)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                    query += " AND created_at < %s"
                    params.append(date_to_obj)
                except ValueError:
                    pass
            
            query += " ORDER BY created_at DESC LIMIT 50"
            
            cur.execute(query, tuple(params))
            alerts_list = cur.fetchall()
            
            # Enrich alerts with portfolio names
            for alert in alerts_list:
                if alert['portfolio_id']:
                    cur.execute("SELECT name FROM portfolios WHERE id = %s", (alert['portfolio_id'],))
                    port = cur.fetchone()
                    alert['portfolio_name'] = port['name'] if port else 'Unknown'
                else:
                    alert['portfolio_name'] = 'Unknown'
            
            cur.execute("SELECT * FROM portfolios")
            all_portfolios = cur.fetchall()
            
    finally:
        put_db_connection(conn)
        
    return render_template('alerts.html',
                         alerts=alerts_list,
                         all_portfolios=all_portfolios,
                         selected_portfolio=portfolio_id,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/alert/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    """Dismiss an alert (soft delete by marking as read)"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM alerts WHERE id = %s", (alert_id,))
            if cur.fetchone():
                cur.execute("DELETE FROM alerts WHERE id = %s", (alert_id,))
                conn.commit()
                flash('Alert dismissed', 'success')
            else:
                flash('Alert not found', 'error')
    except Exception as e:
        conn.rollback()
        flash(f'Error dismissing alert: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    return redirect(request.referrer or url_for('alerts'))

# ================== ANALYTICS ROUTES ==================

@app.route('/analytics')
def analytics():
    """Display analytics and performance charts"""
    conn = get_db_connection()
    portfolio_stats = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM portfolios")
            portfolios = cur.fetchall()
            
            for portfolio in portfolios:
                cur.execute("SELECT COUNT(*) as count FROM holdings WHERE portfolio_id = %s", (portfolio['id'],))
                count = cur.fetchone()['count']
                portfolio_stats.append({
                    'name': portfolio['name'],
                    'holdings': count
                })
    finally:
        put_db_connection(conn)
    
    return render_template('analytics.html', portfolio_stats=portfolio_stats)

# ================== ERROR HANDLERS ==================

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def internal_error(error):
    flash('An internal error occurred', 'error')
    return redirect(url_for('dashboard'))

@app.route('/api/run-workflow', methods=['POST'])
def run_workflow_api():
    token = request.headers.get('Authorization')
    if token != f"Bearer {os.getenv('CRON_SECRET')}":
        return {"error": "Unauthorized"}, 401
    
    try:
        run_root_workflow()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True)
