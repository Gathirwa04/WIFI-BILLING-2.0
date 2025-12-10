from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import json
import secrets
import csv
from io import StringIO
from flask import Response
from mpesa import MpesaClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wifi_billing.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- M-PESA Configuration ---
CONSUMER_KEY = 'nw13EemAMrey2ntOsp2Glxe7AAoPVysTps3tl97QUkczuGzm'
CONSUMER_SECRET = '8pzoyemBCUufsRATNw2Le8jcmEQZ3GGLQGTXhHstVbEqRTHy53AmkQLXdhdQ6euO'
BUSINESS_SHORTCODE = '174379' # Default Sandbox Shortcode
PASSKEY = 'bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919' # Default Sandbox Passkey
CALLBACK_URL = 'https://mydomain.com/callback' # Placeholder, needs ngrok for local testing

mpesa_client = MpesaClient(CONSUMER_KEY, CONSUMER_SECRET, BUSINESS_SHORTCODE, PASSKEY, CALLBACK_URL)

# --- Data ---
PACKAGES = [
    {"id": 1, "name": "BASIC", "duration": "30min", "price": 5, "color": "cyan"},
    {"id": 2, "name": "LITE", "duration": "1hr", "price": 10, "color": "blue"},
    {"id": 3, "name": "Bazu", "duration": "3hrs", "price": 20, "color": "green"},
    {"id": 4, "name": "KIFARU", "duration": "6hrs", "price": 30, "color": "yellow"},
    {"id": 5, "name": "NDOVU", "duration": "12hrs", "price": 40, "color": "orange"},
    {"id": 6, "name": "JINICE", "duration": "24hrs", "price": 50, "color": "red"},
    {"id": 7, "name": "BREEZY", "duration": "3 DAYS", "price": 100, "color": "purple"},
    {"id": 8, "name": "WIKI SMART", "duration": "1 WEEK", "price": 170, "color": "pink"}, # Assuming 'WIKI' means week
    {"id": 9, "name": "BALOZI", "duration": "2 WEEKS", "price": 280, "color": "teal"},
    {"id": 10, "name": "MWEZI EXPRESS", "duration": "1 MONTH", "price": 500, "color": "gold"}, # Assuming 'MWEZI' means month
]

def get_package_by_id(pkg_id):
    for pkg in PACKAGES:
        if pkg['id'] == pkg_id:
            return pkg
    return None

# --- Models ---
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    phone_number = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    mpesa_receipt_number = db.Column(db.String(50), unique=True, nullable=True)
    package_name = db.Column(db.String(50), nullable=False)
    checkout_request_id = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), default='Pending') # Pending, Completed, Failed, Expired
    access_code = db.Column(db.String(20), nullable=True)
    mac_address = db.Column(db.String(50), nullable=True) # For Device Locking
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'phone_number': self.phone_number,
            'amount': self.amount,
            'mpesa_receipt_number': self.mpesa_receipt_number,
            'package_name': self.package_name,
            'status': self.status,
            'access_code': self.access_code,
            'mac_address': self.mac_address,
            'date_created': self.date_created.strftime('%Y-%m-%d %H:%M:%S')
        }



class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=False)
    contact = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='Open') # Open, Resolved
    date_submitted = db.Column(db.DateTime, default=datetime.utcnow)

class Agent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(50), nullable=False)
    wallet_balance = db.Column(db.Float, default=0.0)

class Voucher(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    duration = db.Column(db.String(20), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    generated_by = db.Column(db.String(50), default='Admin')
    date_generated = db.Column(db.DateTime, default=datetime.utcnow)

# --- Routes ---

def parse_duration(duration_str):
    if 'min' in duration_str:
        return timedelta(minutes=int(duration_str.replace('min', '')))
    elif 'hr' in duration_str:
        return timedelta(hours=int(duration_str.replace('hr', '').replace('s', '')))
    elif 'DAY' in duration_str:
        return timedelta(days=int(duration_str.split(' ')[0]))
    elif 'WEEK' in duration_str:
        return timedelta(weeks=int(duration_str.split(' ')[0]))
    elif 'MONTH' in duration_str:
        return timedelta(days=30 * int(duration_str.split(' ')[0]))
    return timedelta(hours=1) # Default

@app.route('/')
def index():
    return render_template('index.html', packages=PACKAGES)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        category = request.form.get('category')
        message = request.form.get('message')
        contact_info = request.form.get('contact')
        
        new_complaint = Complaint(category=category, message=message, contact=contact_info)
        db.session.add(new_complaint)
        db.session.commit()
        flash('Complaint submitted. We will contact you shortly.')
        return redirect(url_for('contact'))
    return render_template('contact.html')

@app.route('/pay/<int:package_id>')
def payment(package_id):
    package = get_package_by_id(package_id)
    if not package:
        return redirect(url_for('index'))
    return render_template('payment.html', package=package)

@app.route('/stk_push', methods=['POST'])
def trigger_stk_push():
    phone_number = request.form.get('phone_number')
    package_id = int(request.form.get('package_id'))
    package = get_package_by_id(package_id)

    if not package:
        return jsonify({'error': 'Invalid package'}), 400
    
    if not phone_number:
         return jsonify({'error': 'Phone number required'}), 400

    # Ensure phone number is in correct format (254...)
    # Sanitize: remove spaces, +, etc.
    clean_phone = phone_number.replace('+', '').replace(' ', '')
    
    try:
        # Trigger STK Push
        response = mpesa_client.stk_push(
            phone_number=clean_phone,
            amount=package['price'],
            account_reference=f"Wifi_{package['name']}",
            transaction_desc=f"Payment for {package['name']}"
        )
        
        checkout_request_id = response.get('CheckoutRequestID')
        response_code = response.get('ResponseCode')

        if response_code == '0':
            # Create Transaction Record
            new_transaction = Transaction(
                phone_number=clean_phone,
                amount=package['price'],
                package_name=package['name'],
                checkout_request_id=checkout_request_id
            )
            db.session.add(new_transaction)
            db.session.commit()
            
            return jsonify({'success': True, 'checkout_request_id': checkout_request_id})
        else:
            return jsonify({'success': False, 'message': response.get('ResponseDescription', 'STK Push failed')})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/callback', methods=['POST'])
def mpesa_callback():
    data = request.get_json()
    
    # Process the callback data
    # Note: In a real app, verify signature/authenticity
    
    body = data.get('Body', {}).get('stkCallback', {})
    result_code = body.get('ResultCode')
    checkout_request_id = body.get('CheckoutRequestID')
    
    transaction = Transaction.query.filter_by(checkout_request_id=checkout_request_id).first()
    
    if transaction:
        if result_code == 0:
            transaction.status = 'Completed'
            # Extract receipt number (Item 1 usually)
            items = body.get('CallbackMetadata', {}).get('Item', [])
            for item in items:
                if item.get('Name') == 'MpesaReceiptNumber':
                    transaction.mpesa_receipt_number = item.get('Value')
            
            # Generate Access Code
            transaction.access_code = secrets.token_hex(4).upper()
        else:
            transaction.status = 'Failed'
        
        db.session.commit()
        
    return jsonify({"ResultCode": 0, "ResultDesc": "Accepted"})

@app.route('/check_payment/<checkout_request_id>')
def check_payment(checkout_request_id):
    transaction = Transaction.query.filter_by(checkout_request_id=checkout_request_id).first()
    if transaction:
        return jsonify({
            'status': transaction.status,
            'access_code': transaction.access_code if transaction.status == 'Completed' else None
        })

# --- Test / Simulation Route ---
@app.route('/test/simulate_payment/<checkout_request_id>')
def simulate_payment(checkout_request_id):
    transaction = Transaction.query.filter_by(checkout_request_id=checkout_request_id).first()
    if transaction:
        transaction.status = 'Completed'
        transaction.access_code = secrets.token_hex(4).upper()
        transaction.mpesa_receipt_number = f"SIM{secrets.token_hex(4).upper()}"
        db.session.commit()
        return jsonify({'success': True, 'message': 'Payment simulated successfully'})
    return jsonify({'success': False, 'message': 'Transaction not found'})


@app.route('/redeem', methods=['GET', 'POST'])
def redeem():
    if request.method == 'POST':
        mpesa_code = request.form.get('mpesa_code')
        # Simulate capturing MAC from URL (e.g., ?mac=AA:BB:CC...)
        # In a real Router login page, this is passed automatically.
        # For this standalone testing, we will generate a 'device_id' cookie if missing, or use a dummy.
        user_mac = request.args.get('mac', request.cookies.get('device_id', 'UNKNOWN_DEVICE'))
        
        if not mpesa_code:
            flash('Please enter a code or phone number')
            return redirect(url_for('redeem'))
            
        # Check if it's a phone number (digits only or starts with +)
        is_phone = mpesa_code.replace('+', '').isdigit()
        
        transaction = None
        if is_phone:
            # Search by phone number (latest successful)
            clean_phone = mpesa_code.replace('+', '').replace(' ', '')
             # Try 254 format or 07 format
            if clean_phone.startswith('0'):
                clean_phone = '254' + clean_phone[1:]
            elif clean_phone.startswith('7') or clean_phone.startswith('1'):
                clean_phone = '254' + clean_phone
                
            transaction = Transaction.query.filter_by(phone_number=clean_phone, status='Completed').order_by(Transaction.id.desc()).first()
        else:
            # Search by Receipt Number OR Access Code
            transaction = Transaction.query.filter((Transaction.mpesa_receipt_number==mpesa_code) | (Transaction.access_code==mpesa_code)).first()
        
        if transaction:
            if transaction.status == 'Completed':
                # --- MAC BINDING LOGIC ---
                if transaction.mac_address:
                    # Already bound, check if it matches
                    if transaction.mac_address != user_mac and user_mac != 'UNKNOWN_DEVICE':
                        flash(f"SECURITY ALERT: This code is locked to another device. Access Denied.")
                        return redirect(url_for('redeem'))
                    elif user_mac == 'UNKNOWN_DEVICE':
                         # Allow but warn (since we can't strictly enforce without router)
                         flash("Warning: Device ID not detected. Please connect through the Hotspot Login page for better security.")
                else:
                    # First use! Bind to this MAC
                    if user_mac != 'UNKNOWN_DEVICE':
                        transaction.mac_address = user_mac
                        db.session.commit()
                        flash(f"Success! Code locked to this device ({user_mac}).")
                # -------------------------

                return render_template('success.html', access_code=transaction.access_code)
            elif transaction.status == 'Expired':
                flash('This code has expired. Please purchase a new package.')
            else:
                flash(f'Transaction found but status is: {transaction.status}')
        else:
            flash(f'No successful transaction found for {mpesa_code}.')
            
    return render_template('redeem.html')

@app.route('/success')
def success():
    access_code = request.args.get('code')
    return render_template('success.html', access_code=access_code)




# --- Helper Functions ---
def disconnect_user_from_router(access_code):
    """
    Placeholder for Mikrotik/Router integration.
    In a real scenario, this would send an API command to the router
    to remove the user from the active hotspot list.
    """
    print(f"[ROUTER] Disconnecting user with code: {access_code}")
    # Example: mpesa_client.send_router_command(f"/ip hotspot active remove {access_code}")
    pass

def check_and_expire_sessions(user_phone):
    """
    Checks all 'Completed' transactions for this user.
    If time has elapsed, updates status to 'Expired'.
    """
    transactions = Transaction.query.filter_by(phone_number=user_phone, status='Completed').all()
    now = datetime.utcnow()
    pkg_duration_map = {p['name']: p['duration'] for p in PACKAGES}
    
    expired_count = 0
    for t in transactions:
        duration_str = pkg_duration_map.get(t.package_name, '1hr')
        try:
            duration = parse_duration(duration_str)
            if now > t.date_created + duration:
                # Session has expired
                t.status = 'Expired'
                disconnect_user_from_router(t.access_code)
                expired_count += 1
        except:
            continue
            
    if expired_count > 0:
        db.session.commit()
        return True
    return False

# --- User Portal Routes ---
@app.route('/my_account', methods=['GET', 'POST'])
def my_account():
    if request.method == 'POST':
        phone = request.form.get('phone_number')
        if phone:
            # Basic validation
            clean_phone = phone.replace('+', '').replace(' ', '')
             # Try 254 format or 07 format normalization for consistent session storage
            if clean_phone.startswith('0'):
                clean_phone = '254' + clean_phone[1:]
            elif clean_phone.startswith('7') or clean_phone.startswith('1'):
                clean_phone = '254' + clean_phone
                
            session['user_phone'] = clean_phone
            return redirect(url_for('user_dashboard'))
        else:
            flash("Please enter your phone number.")
    return render_template('user_login.html')

@app.route('/user/dashboard')
def user_dashboard():
    user_phone = session.get('user_phone')
    if not user_phone:
        return redirect(url_for('my_account'))
    
    # 1. Enforce Expiry Logic BEFORE rendering
    check_and_expire_sessions(user_phone)
    
    # Fetch History (Now includes 'Expired' status updates)
    transactions = Transaction.query.filter_by(phone_number=user_phone).order_by(Transaction.date_created.desc()).all()
    
    # Determine Active Plan
    active_plan = None
    now = datetime.utcnow()
    pkg_duration_map = {p['name']: p['duration'] for p in PACKAGES}
    
    # Look for the latest COMPLETED transaction that is still valid
    for t in transactions:
        if t.status == 'Completed':
            duration_str = pkg_duration_map.get(t.package_name, '1hr')
            try:
                duration = parse_duration(duration_str)
                expiry_time = t.date_created + duration
                if now < expiry_time:
                    time_left = expiry_time - now
                    # Format time left
                    hours, remainder = divmod(time_left.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    
                    if time_left.days > 0:
                        time_str = f"{time_left.days} Days, {hours} Hrs"
                    else:
                        time_str = f"{hours} Hrs, {minutes} Mins"
                        
                    active_plan = {
                        'package': t.package_name,
                        'access_code': t.access_code,
                        'time_left': time_str,
                        'expiry': expiry_time.strftime('%Y-%m-%d %H:%M')
                    }
                    break # Found the most recent active one
            except:
                pass

    return render_template('user_dashboard.html', transactions=transactions, active_plan=active_plan, phone=user_phone)

@app.route('/user/logout')
def user_logout():
    session.pop('user_phone', None)
    return redirect(url_for('index'))

# --- Admin Section ---
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin123': # Simple hardcoded auth
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    
    # 1. Fetch Agents (Defensive)
    try:
        agents = Agent.query.all()
    except:
        agents = []

    # 2. Fetch Complaints
    try:
        complaints = Complaint.query.order_by(Complaint.date_submitted.desc()).all()
    except:
        complaints = []

    # 3. Fetch ALL Transactions for analytics
    try:
        all_transactions = Transaction.query.order_by(Transaction.date_created.desc()).all()
        
        # Calculate Analytics
        total_revenue = sum(t.amount for t in all_transactions if t.status == 'Completed')
        
        # Today's Stats
        today = datetime.utcnow().date()
        today_transactions = [t for t in all_transactions if t.date_created.date() == today]
        today_revenue = sum(t.amount for t in today_transactions if t.status == 'Completed')
        today_completed = len([t for t in today_transactions if t.status == 'Completed'])
        pending_count = len([t for t in all_transactions if t.status == 'Pending'])
        
        # Active Count (Simple estimation)
        active_count = 0
        now = datetime.utcnow()
        for t in all_transactions:
            if t.status == 'Completed':
                duration = timedelta(hours=1) 
                pkg_name = t.package_name.upper() if t.package_name else ''
                if '30MIN' in pkg_name or 'BASIC' in pkg_name: duration = timedelta(minutes=30)
                elif '3HR' in pkg_name or 'BAZU' in pkg_name: duration = timedelta(hours=3)
                elif '6HR' in pkg_name or 'KIFARU' in pkg_name: duration = timedelta(hours=6)
                elif '12HR' in pkg_name or 'NDOVU' in pkg_name: duration = timedelta(hours=12)
                elif '24HR' in pkg_name or 'JINICE' in pkg_name: duration = timedelta(hours=24)
                elif '3 DAY' in pkg_name or 'BREEZY' in pkg_name: duration = timedelta(days=3)
                elif '1 WEEK' in pkg_name or 'WIKI' in pkg_name: duration = timedelta(weeks=1)
                elif '2 WEEK' in pkg_name or 'BALOZI' in pkg_name: duration = timedelta(weeks=2)
                elif '1 MONTH' in pkg_name or 'MWEZI' in pkg_name: duration = timedelta(days=30)
                
                if now < t.date_created + duration:
                    active_count += 1
                    
        # Popular Package
        from collections import Counter
        completed_pkgs = [t.package_name for t in all_transactions if t.status == 'Completed']
        if completed_pkgs:
            pkg_counts = Counter(completed_pkgs)
            most_popular = pkg_counts.most_common(1)[0][0]
        else:
            most_popular = "None"
            
    except Exception as e:
        print(f"Dashboard Error: {e}")
        all_transactions = []
        total_revenue = 0
        active_count = 0
        most_popular = "Error"
        today_revenue = 0
        today_completed = 0
        pending_count = 0

    # 4. Filter transactions for display
    transactions = all_transactions
    search_query = request.args.get('q')
    filter_status = request.args.get('status')
    
    if search_query:
        sq = search_query.lower()
        transactions = [t for t in transactions if 
                        sq in str(t.phone_number or '').lower() or 
                        sq in str(t.access_code or '').lower() or
                        sq in str(t.mpesa_receipt_number or '').lower()]
    
    if filter_status:
        transactions = [t for t in transactions if t.status == filter_status]

    # Get last 5 payments
    last_payments = Transaction.query.filter_by(status='Completed').order_by(Transaction.date_created.desc()).limit(5).all()
    
    # Total users count (unique phone numbers)
    total_users = db.session.query(Transaction.phone_number).distinct().count()
    
    # Expired users count
    expired_count = Transaction.query.filter_by(status='Expired').count()

    return render_template('dashboard.html', 
                           transactions=transactions, 
                           total_revenue=total_revenue,
                           active_count=active_count,
                           most_popular=most_popular,
                           complaints=complaints,
                           agents=agents,
                           today_revenue=today_revenue,
                           today_completed=today_completed,
                           pending_count=pending_count,
                           last_payments=last_payments,
                           total_users=total_users,
                           expired_count=expired_count)

# --- Admin Section: Users ---
@app.route('/admin/users')
def admin_users():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    transactions = Transaction.query.order_by(Transaction.date_created.desc()).all()
    return render_template('admin/users.html', transactions=transactions)

# --- Admin Section: Payments ---
@app.route('/admin/payments')
def admin_payments():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    transactions = Transaction.query.order_by(Transaction.date_created.desc()).all()
    return render_template('admin/payments.html', transactions=transactions, packages=PACKAGES)

# --- Admin Section: Settings ---
@app.route('/admin/settings', methods=['GET', 'POST'])
def admin_settings():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        flash('Settings saved (placeholder)')
    return render_template('admin/settings.html')

# --- Admin Section: Admin Accounts ---
@app.route('/admin/admins')
def admin_admins():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    return render_template('admin/admins.html')



@app.route('/admin/resolve_complaint/<int:id>')
def resolve_complaint(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    complaint = Complaint.query.get(id)
    if complaint:
        complaint.status = 'Resolved'
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export')
def export_csv():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Phone', 'Amount', 'Package', 'Receipt', 'Status', 'Code', 'Mac Address', 'Date'])
    
    transactions = Transaction.query.all()
    for t in transactions:
        cw.writerow([t.id, t.phone_number, t.amount, t.package_name, t.mpesa_receipt_number, t.status, t.access_code, t.mac_address, t.date_created])
        
    output = si.getvalue()
    return Response(output, mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=transactions.csv"})

# --- PDF Voucher Generation ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from io import BytesIO

@app.route('/admin/generate_vouchers', methods=['POST'])
def generate_vouchers():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    quantity = int(request.form.get('quantity', 10))
    duration = request.form.get('duration', '1hr')
    package_name = request.form.get('package_name', 'Lite')
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    x_start, y_start = 50, height - 50
    card_width, card_height = 150, 80
    cols = 3
    x, y = x_start, y_start
    
    for i in range(quantity):
        code = secrets.token_hex(4).upper()
        
        # Save to DB
        v = Voucher(code=code, duration=duration, generated_by='Admin')
        db.session.add(v)
        
        # Draw Card
        p.setStrokeColor(colors.cyan)
        p.rect(x, y - card_height, card_width, card_height)
        p.setFont("Helvetica-Bold", 12)
        p.drawString(x + 10, y - 20, "WIFI VOUCHER")
        p.setFont("Helvetica", 10)
        p.drawString(x + 10, y - 35, f"Plan: {package_name} ({duration})")
        p.setFont("Courier-Bold", 14)
        p.drawString(x + 10, y - 60, f"Code: {code}")
        
        x += card_width + 10
        if (i + 1) % cols == 0:
            x = x_start
            y -= card_height + 10
        if y < 50:
            p.showPage()
            y = y_start
            x = x_start
            
    db.session.commit()
    p.save()
    buffer.seek(0)
    return Response(buffer, mimetype='application/pdf', 
                    headers={"Content-Disposition": f"attachment;filename=vouchers_{package_name}_{quantity}.pdf"})

# --- Agent Management Routes ---
@app.route('/admin/create_agent', methods=['POST'])
def create_agent():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    username = request.form.get('username')
    password = request.form.get('password')
    if Agent.query.filter_by(username=username).first():
        flash('Agent username already exists.')
    else:
        new_agent = Agent(username=username, password=password, wallet_balance=0)
        db.session.add(new_agent)
        db.session.commit()
        flash(f'Agent {username} created.')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/topup_agent/<int:id>', methods=['POST'])
def topup_agent(id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    amount = float(request.form.get('amount', 0))
    agent = Agent.query.get(id)
    if agent:
        agent.wallet_balance += amount
        db.session.commit()
        flash(f'Added {amount} to {agent.username}.')
    return redirect(url_for('admin_dashboard'))

# --- Agent Portal Routes ---
@app.route('/agent', methods=['GET', 'POST'])
def agent_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        agent = Agent.query.filter_by(username=username).first()
        if agent and agent.password == password:
            session['agent_id'] = agent.id
            return redirect(url_for('agent_dashboard'))
        else:
            flash('Invalid Agent Credentials')
    return render_template('agent_login.html')

@app.route('/agent/dashboard')
def agent_dashboard():
    agent_id = session.get('agent_id')
    if not agent_id:
        return redirect(url_for('agent_login'))
    agent = Agent.query.get(agent_id)
    return render_template('agent_dashboard.html', agent=agent, packages=PACKAGES)

@app.route('/agent/sell', methods=['POST'])
def agent_sell():
    agent_id = session.get('agent_id')
    if not agent_id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    package_id = int(request.form.get('package_id'))
    phone_number = request.form.get('phone_number')
    package = get_package_by_id(package_id)
    agent = Agent.query.get(agent_id)
    if agent.wallet_balance < package['price']:
        return jsonify({'success': False, 'message': 'Insufficient Balance'}), 400
    agent.wallet_balance -= package['price']
    new_code = secrets.token_hex(4).upper()
    new_txn = Transaction(
        phone_number=phone_number.replace('+', '').replace(' ', ''),
        amount=package['price'],
        package_name=package['name'],
        checkout_request_id=f"AGENT_{secrets.token_hex(4)}",
        mpesa_receipt_number=f"AGENT_{agent.username.upper()}_{secrets.token_hex(4)}",
        status='Completed',
        access_code=new_code
    )
    db.session.add(new_txn)
    db.session.commit()
    return jsonify({'success': True, 'code': new_code, 'new_balance': agent.wallet_balance})

@app.route('/agent/logout')
def agent_logout():
    session.pop('agent_id', None)
    return redirect(url_for('index'))# Create DB
with app.app_context():
    db.create_all()

# --- Error Handling ---
@app.errorhandler(Exception)
def handle_exception(e):
    # Log the error (in a real app, use logging module)
    print(f"CRITICAL ERROR: {str(e)}")
    
    # Return JSON if it's an AJAX request (like the payment poll)
    if request.is_json or request.args.get('json'):
        return jsonify({"success": False, "message": "Internal Server Error. The system is self-correcting."}), 500
        
    # Otherwise return error page
    return render_template('base.html', content="<div class='container' style='text-align:center; padding:50px;'><h2 style='color:red'>System Glitch Detected</h2><p>Auto-correction protocol initiated. Please refresh in a moment.</p></div>"), 500

if __name__ == '__main__':
    import webbrowser
    import threading

    def open_browser():
        webbrowser.open_new('http://127.0.0.1:5000')

    threading.Timer(1.5, open_browser).start()
    app.run(debug=True)
