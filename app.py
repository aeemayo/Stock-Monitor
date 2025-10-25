import os
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv
from sqlalchemy import text, desc
from db import init_db, get_session
from scheduler import start_scheduler
from roma.workflow import run_root_workflow
from models import Portfolio, Holding, Alert

load_dotenv()

app = Flask(__name__, template_folder='templates')
app.config['DATABASE_URL'] = os.getenv('DATABASE_URL', 'sqlite:///./stocks.db')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize on startup
def initialize_app():
    init_db(app.config['DATABASE_URL'])
    # start the background scheduler which will run ROMA daily
    start_scheduler(app)

# ================== DASHBOARD ROUTES ==================

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Display all portfolios and create portfolio form"""
    session = get_session()
    portfolios = session.query(Portfolio).all()
    
    # Enrich portfolios with holdings count
    for portfolio in portfolios:
        portfolio.holdings = session.query(Holding).filter(Holding.portfolio_id == portfolio.id).all()
    
    total_holdings = session.query(Holding).count()
    
    return render_template('dashboard.html', 
                         portfolios=portfolios,
                         total_holdings=total_holdings)

# ================== PORTFOLIO ROUTES ==================

@app.route('/portfolio/create', methods=['POST'])
def create_portfolio():
    """Create a new portfolio"""
    session = get_session()
    try:
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Portfolio name is required', 'error')
            return redirect(url_for('dashboard'))
        
        portfolio = Portfolio(name=name)
        session.add(portfolio)
        session.commit()
        
        flash(f'Portfolio "{name}" created successfully!', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error creating portfolio: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('dashboard'))

@app.route('/portfolio/<int:portfolio_id>')
def view_portfolio(portfolio_id):
    """View portfolio details and holdings"""
    session = get_session()
    portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    
    if not portfolio:
        flash('Portfolio not found', 'error')
        return redirect(url_for('dashboard'))
    
    holdings = session.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()
    total_shares = sum(h.shares for h in holdings)
    unique_tickers = len(set(h.ticker for h in holdings))
    
    # Get recent alerts for this portfolio
    recent_alerts = session.query(Alert).filter(
        Alert.portfolio_id == portfolio_id
    ).order_by(desc(Alert.created_at)).limit(5).count()
    
    return render_template('portfolio.html',
                         portfolio=portfolio,
                         holdings=holdings,
                         total_shares=total_shares,
                         unique_tickers=unique_tickers,
                         recent_alerts=recent_alerts)

@app.route('/portfolio/<int:portfolio_id>/delete', methods=['POST'])
def delete_portfolio(portfolio_id):
    """Delete a portfolio and all associated holdings and alerts"""
    session = get_session()
    try:
        portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        
        if not portfolio:
            flash('Portfolio not found', 'error')
            return redirect(url_for('dashboard'))
        
        portfolio_name = portfolio.name
        
        # Delete holdings
        session.query(Holding).filter(Holding.portfolio_id == portfolio_id).delete()
        
        # Delete alerts
        session.query(Alert).filter(Alert.portfolio_id == portfolio_id).delete()
        
        # Delete portfolio
        session.delete(portfolio)
        session.commit()
        
        flash(f'Portfolio "{portfolio_name}" deleted successfully', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error deleting portfolio: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('dashboard'))

@app.route('/portfolio/<int:portfolio_id>/edit')
def edit_portfolio(portfolio_id):
    """Edit portfolio form (placeholder)"""
    session = get_session()
    portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
    
    if not portfolio:
        flash('Portfolio not found', 'error')
        return redirect(url_for('dashboard'))
    
    # TODO: Create edit template
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

# ================== HOLDINGS ROUTES ==================

@app.route('/portfolio/<int:portfolio_id>/holding/create', methods=['POST'])
def create_holding(portfolio_id):
    """Add a holding to a portfolio"""
    session = get_session()
    try:
        portfolio = session.query(Portfolio).filter(Portfolio.id == portfolio_id).first()
        
        if not portfolio:
            flash('Portfolio not found', 'error')
            return redirect(url_for('dashboard'))
        
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
        
        holding = Holding(
            portfolio_id=portfolio_id,
            ticker=ticker,
            shares=shares
        )
        session.add(holding)
        session.commit()
        
        flash(f'Added {shares} shares of {ticker} to portfolio', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error adding holding: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

@app.route('/holding/<int:holding_id>/delete', methods=['POST'])
def delete_holding(holding_id):
    """Delete a holding from a portfolio"""
    session = get_session()
    try:
        holding = session.query(Holding).filter(Holding.id == holding_id).first()
        
        if not holding:
            flash('Holding not found', 'error')
            return redirect(url_for('dashboard'))
        
        portfolio_id = holding.portfolio_id
        ticker = holding.ticker
        
        session.delete(holding)
        session.commit()
        
        flash(f'Removed {ticker} from portfolio', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error deleting holding: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(url_for('view_portfolio', portfolio_id=portfolio_id))

@app.route('/holding/<int:holding_id>/edit')
def edit_holding(holding_id):
    """Edit holding form (placeholder)"""
    session = get_session()
    holding = session.query(Holding).filter(Holding.id == holding_id).first()
    
    if not holding:
        flash('Holding not found', 'error')
        return redirect(url_for('dashboard'))
    
    # TODO: Create edit template
    return redirect(url_for('view_portfolio', portfolio_id=holding.portfolio_id))

# ================== ALERTS ROUTES ==================

@app.route('/alerts')
def alerts():
    """Display alerts with filtering options"""
    session = get_session()
    
    # Get filter parameters
    portfolio_id = request.args.get('portfolio_id', type=int)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Build query
    query = session.query(Alert).order_by(desc(Alert.created_at))
    
    if portfolio_id:
        query = query.filter(Alert.portfolio_id == portfolio_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(Alert.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(Alert.created_at < date_to_obj)
        except ValueError:
            pass
    
    alerts_list = query.limit(50).all()
    
    # Enrich alerts with portfolio names
    for alert in alerts_list:
        portfolio = session.query(Portfolio).filter(Portfolio.id == alert.portfolio_id).first()
        alert.portfolio_name = portfolio.name if portfolio else 'Unknown'
    
    # Get all portfolios for filter dropdown
    all_portfolios = session.query(Portfolio).all()
    selected_portfolio = portfolio_id
    
    return render_template('alerts.html',
                         alerts=alerts_list,
                         all_portfolios=all_portfolios,
                         selected_portfolio=selected_portfolio,
                         date_from=date_from,
                         date_to=date_to)

@app.route('/alert/<int:alert_id>/dismiss', methods=['POST'])
def dismiss_alert(alert_id):
    """Dismiss an alert (soft delete by marking as read)"""
    session = get_session()
    try:
        # This could be implemented by adding an 'is_read' flag to alerts
        # For now, just delete it
        alert = session.query(Alert).filter(Alert.id == alert_id).first()
        
        if alert:
            session.delete(alert)
            session.commit()
            flash('Alert dismissed', 'success')
        else:
            flash('Alert not found', 'error')
    except Exception as e:
        session.rollback()
        flash(f'Error dismissing alert: {str(e)}', 'error')
    finally:
        session.close()
    
    return redirect(request.referrer or url_for('alerts'))

# ================== ANALYTICS ROUTES ==================

@app.route('/analytics')
def analytics():
    """Display analytics and performance charts"""
    session = get_session()
    
    # Get portfolio statistics
    portfolios = session.query(Portfolio).all()
    portfolio_stats = []
    
    for portfolio in portfolios:
        holdings_count = session.query(Holding).filter(
            Holding.portfolio_id == portfolio.id
        ).count()
        portfolio_stats.append({
            'name': portfolio.name,
            'holdings': holdings_count
        })
    
    return render_template('analytics.html', portfolio_stats=portfolio_stats)

# ================== ERROR HANDLERS ==================

@app.errorhandler(404)
def not_found(error):
    return redirect(url_for('dashboard'))

@app.errorhandler(500)
def internal_error(error):
    flash('An internal error occurred', 'error')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    initialize_app()
    app.run(debug=True)
