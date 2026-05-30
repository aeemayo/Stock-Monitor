import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit
from flask import Flask, render_template, request, redirect, url_for, flash, session
from dotenv import load_dotenv
from db import init_db, get_db_connection, put_db_connection
from psycopg2.extras import RealDictCursor
from scheduler import start_scheduler
from roma.workflow import run_root_workflow
import bcrypt
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'postgresql://localhost/stocks')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
_initialized = False

# ================== FLASK-LOGIN SETUP ==================

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please sign in to access this page.'
login_manager.login_message_category = 'error'

class User(UserMixin):
    """User model that wraps a database row dict for Flask-Login."""
    def __init__(self, user_dict):
        self.id = user_dict['id']
        self.username = user_dict['username']
        self.email = user_dict['email']
        self.created_at = user_dict.get('created_at')

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (int(user_id),))
            row = cur.fetchone()
            if row:
                return User(row)
    finally:
        put_db_connection(conn)
    return None

# Initialize on startup
def initialize_app():
    global _initialized
    if _initialized:
        return
    init_db(app.config['DATABASE_URL'])
    # Don't start scheduler on serverless
    if os.getenv('ENVIRONMENT') != 'vercel' and not os.getenv('VERCEL'):
        start_scheduler(app)
    _initialized = True

def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token

def is_safe_redirect(target):
    if not target:
        return False
    ref = urlsplit(request.host_url)
    test = urlsplit(target)
    return not test.netloc or (test.scheme in ('http', 'https') and test.netloc == ref.netloc)

@app.before_request
def prepare_request():
    initialize_app()
    if request.method == 'POST' and request.endpoint != 'run_workflow_api':
        expected = session.get('_csrf_token')
        submitted = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, submitted):
            flash('Your session expired. Please try again.', 'error')
            return redirect(request.referrer if is_safe_redirect(request.referrer) else url_for('dashboard'))

@app.context_processor
def inject_security_helpers():
    return {'csrf_token': csrf_token}

# ================== AUTH ROUTES ==================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        errors = []
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not email or '@' not in email:
            errors.append('A valid email is required.')
        if not password or len(password) < 6:
            errors.append('Password must be at least 6 characters.')
        if password != confirm_password:
            errors.append('Passwords do not match.')
        
        if errors:
            for err in errors:
                flash(err, 'error')
            return render_template('register.html', username=username, email=email)
        
        # Check for existing user
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
                if cur.fetchone():
                    flash('Username or email already taken.', 'error')
                    return render_template('register.html', username=username, email=email)
                
                # Hash password and insert
                pw_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                cur.execute(
                    "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s) RETURNING id",
                    (username, email, pw_hash)
                )
                new_user = cur.fetchone()
            conn.commit()
            
            # Auto-login after registration
            user = User({'id': new_user['id'], 'username': username, 'email': email})
            login_user(user)
            flash(f'Welcome aboard, {username}!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            conn.rollback()
            flash(f'Registration error: {str(e)}', 'error')
        finally:
            put_db_connection(conn)
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        
        if not identifier or not password:
            flash('Please fill in all fields.', 'error')
            return render_template('login.html', identifier=identifier)
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM users WHERE username = %s OR email = %s",
                    (identifier, identifier.lower())
                )
                row = cur.fetchone()
        finally:
            put_db_connection(conn)
        
        if row and bcrypt.checkpw(password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            user = User(row)
            login_user(user, remember=True)
            flash(f'Welcome back, {user.username}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page if is_safe_redirect(next_page) else url_for('dashboard'))
        else:
            flash('Invalid username/email or password.', 'error')
            return render_template('login.html', identifier=identifier)
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'success')
    return redirect(url_for('login'))

# ================== DASHBOARD ROUTES ==================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Display all portfolios and create portfolio form"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolios WHERE user_id = %s ORDER BY id", (current_user.id,))
            portfolios = cur.fetchall()
            
            for portfolio in portfolios:
                cur.execute("SELECT * FROM holdings WHERE portfolio_id = %s", (portfolio['id'],))
                portfolio['holdings'] = cur.fetchall()
            
            cur.execute("""
                SELECT COUNT(*) as count FROM holdings h
                JOIN portfolios p ON h.portfolio_id = p.id
                WHERE p.user_id = %s
            """, (current_user.id,))
            row = cur.fetchone()
            total_holdings = row['count'] if row else 0
    finally:
        put_db_connection(conn)
        
    return render_template('dashboard.html', 
                         portfolios=portfolios,
                         total_holdings=total_holdings)

# ================== PORTFOLIO ROUTES ==================

@app.route('/portfolio/create', methods=['POST'])
@login_required
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
            cur.execute("INSERT INTO portfolios (name, description, user_id) VALUES (%s, %s, %s)", (name, description, current_user.id))
        conn.commit()
        
        flash(f'Portfolio "{name}" created successfully!', 'success')
    except Exception as e:
        conn.rollback()
        flash(f'Error creating portfolio: {str(e)}', 'error')
    finally:
        put_db_connection(conn)
    
    return redirect(url_for('dashboard'))

@app.route('/portfolio/<int:portfolio_id>')
@login_required
def view_portfolio(portfolio_id):
    """View portfolio details and holdings"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM portfolios WHERE id = %s AND user_id = %s", (portfolio_id, current_user.id))
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
@login_required
def delete_portfolio(portfolio_id):
    """Delete a portfolio and all associated holdings and alerts"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT name FROM portfolios WHERE id = %s AND user_id = %s", (portfolio_id, current_user.id))
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
@login_required
def edit_portfolio(portfolio_id):
    """Edit portfolio form (placeholder)"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id FROM portfolios WHERE id = %s AND user_id = %s", (portfolio_id, current_user.id))
            if not cur.fetchone():
                flash('Portfolio not found', 'error')
                return redirect(url_for('dashboard'))
    finally:
        put_db_connection(conn)
    
    # TODO: Create edit template
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

# ================== HOLDINGS ROUTES ==================

@app.route('/portfolio/<int:portfolio_id>/holding/create', methods=['POST'])
@login_required
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
            cur.execute("SELECT id FROM portfolios WHERE id = %s AND user_id = %s", (portfolio_id, current_user.id))
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
@login_required
def delete_holding(holding_id):
    """Delete a holding from a portfolio"""
    conn = get_db_connection()
    portfolio_id = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify the holding belongs to the current user's portfolio
            cur.execute("""
                SELECT h.portfolio_id, h.ticker FROM holdings h
                JOIN portfolios p ON h.portfolio_id = p.id
                WHERE h.id = %s AND p.user_id = %s
            """, (holding_id, current_user.id))
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
@login_required
def edit_holding(holding_id):
    """Edit holding form (placeholder)"""
    conn = get_db_connection()
    portfolio_id = None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT h.portfolio_id FROM holdings h
                JOIN portfolios p ON h.portfolio_id = p.id
                WHERE h.id = %s AND p.user_id = %s
            """, (holding_id, current_user.id))
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
@login_required
def alerts():
    """Display alerts with filtering options"""
    portfolio_id = request.args.get('portfolio_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT a.* FROM alerts a
                JOIN portfolios p ON a.portfolio_id = p.id
                WHERE p.user_id = %s
            """
            params = [current_user.id]
            
            if portfolio_id:
                query += " AND a.portfolio_id = %s"
                params.append(portfolio_id)
            
            if date_from:
                try:
                    date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
                    query += " AND a.created_at >= %s"
                    params.append(date_from_obj)
                except ValueError:
                    pass
            
            if date_to:
                try:
                    date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
                    query += " AND a.created_at < %s"
                    params.append(date_to_obj)
                except ValueError:
                    pass
            
            query += " ORDER BY a.created_at DESC LIMIT 50"
            
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
            
            cur.execute("SELECT * FROM portfolios WHERE user_id = %s", (current_user.id,))
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
@login_required
def dismiss_alert(alert_id):
    """Dismiss an alert (soft delete by marking as read)"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Verify ownership
            cur.execute("""
                SELECT a.id FROM alerts a
                JOIN portfolios p ON a.portfolio_id = p.id
                WHERE a.id = %s AND p.user_id = %s
            """, (alert_id, current_user.id))
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
@login_required
def analytics():
    """Display analytics and performance charts"""
    conn = get_db_connection()
    portfolio_stats = []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM portfolios WHERE user_id = %s", (current_user.id,))
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

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')

@app.route('/support')
@login_required
def support():
    return render_template('support.html')

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
    cron_secret = os.getenv('CRON_SECRET')
    if not cron_secret:
        return {"error": "CRON_SECRET is not configured"}, 503

    token = request.headers.get('Authorization')
    expected = f"Bearer {cron_secret}"
    if not token or not secrets.compare_digest(token, expected):
        return {"error": "Unauthorized"}, 401
    
    try:
        run_root_workflow()
        return {"status": "success"}
    except Exception as e:
        return {"error": str(e)}, 500

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True)
