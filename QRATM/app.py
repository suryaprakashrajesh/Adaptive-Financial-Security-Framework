from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_file
import cv2
import numpy as np
from pyzbar.pyzbar import decode
import base64
import os
from datetime import datetime
from functools import wraps
import qrcode
from io import BytesIO
import logging
from werkzeug.utils import secure_filename
import json
import csv
import io

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'qratm_secret_key'  # For session management
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Data file path
DATA_FILE = 'qratm_data.json'

# Global variables
users = {}
atm_balance = 50000.00
atm_history = []
user_history = {}

def load_data():
    """Load data from JSON file"""
    global users, atm_balance, atm_history, user_history
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                users = data.get('users', {})
                atm_balance = data.get('atm_balance', 50000.00)
                atm_history = data.get('atm_history', [])
                user_history = data.get('user_history', {})
        except Exception as e:
            app.logger.error(f"Error loading data: {str(e)}")

def save_data():
    """Save data to JSON file"""
    try:
        data = {
            'users': users,
            'atm_balance': atm_balance,
            'atm_history': atm_history,
            'user_history': user_history,
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        app.logger.info("Data saved successfully")
    except Exception as e:
        app.logger.error(f"Error saving data: {str(e)}")

# Load initial data
load_data()

# Initialize default admin user if not exists
if 'admin' not in users:
    users['admin'] = {
        'password': 'admin123',
        'role': 'admin'  # Admin is ATM administrator, no balance needed
    }
    save_data()

# Initialize some default users if not exists
default_users = {
    'Surya': {'password': 'user123', 'role': 'user', 'balance': 15000.00},
    'user2': {'password': 'user123', 'role': 'user', 'balance': 3000.00},
    'Deepa': {'password': 'user123', 'role': 'user', 'balance': 3000.00}

}

for username, user_data in default_users.items():
    if username not in users:
        users[username] = user_data
        save_data()

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or users[session['username']]['role'] != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# User required decorator
def user_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login first', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username in users and users[username]['password'] == password:
            session['username'] = username
            session['role'] = users[username]['role']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('scan'))

@app.route('/scan', methods=['GET', 'POST'])
def scan():
    if request.method == 'POST':
        try:
            # Handle file upload
            if 'qr_image' in request.files:
                file = request.files['qr_image']
                if file and file.filename:
                    # Save the file temporarily
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    
                    # Process the QR code
                    result = process_qr_code(filepath)
                    
                    # Clean up the temporary file
                    os.remove(filepath)
                    
                    if result:
                        if result.get('is_used'):
                            return render_template('scan.html', error='This QR code has already been used. Please generate a new one.')
                        return redirect(url_for('confirm', name=result['name'], 
                                             amount=result['amount'], 
                                             pin=result['pin']))
                    return render_template('scan.html', error='No valid QR code found. Please try again with a clearer image.')
            
            # Handle camera input (base64 image)
            elif 'image_data' in request.form:
                # Get base64 image data
                image_data = request.form['image_data']
                if image_data:
                    # Remove the data URL prefix if present
                    if ',' in image_data:
                        image_data = image_data.split(',')[1]
                    
                    # Decode base64 image
                    image_bytes = base64.b64decode(image_data)
                    nparr = np.frombuffer(image_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if img is not None:
                        # Process the QR code
                        result = process_qr_code(img)
                        if result:
                            if result.get('is_used'):
                                return jsonify({
                                    'success': False,
                                    'error': 'This QR code has already been used. Please generate a new one.'
                                })
                            return jsonify({
                                'success': True,
                                'redirect': url_for('confirm', 
                                                  name=result['name'],
                                                  amount=result['amount'],
                                                  pin=result['pin'])
                            })
                        return jsonify({
                            'success': False,
                            'error': 'No valid QR code found. Please try again with a clearer image.'
                        })
            
            return render_template('scan.html', error='No image data received.')
            
        except Exception as e:
            app.logger.error(f"Error processing QR code: {str(e)}")
            return render_template('scan.html', error='An error occurred while processing the QR code.')
    
    return render_template('scan.html')

def process_qr_code(image_source):
    """
    Process QR code from either a file path or an image array
    Returns a dictionary with name, amount, pin, and timestamp if successful, None otherwise
    """
    try:
        # Read image if it's a file path
        if isinstance(image_source, str):
            img = cv2.imread(image_source)
        else:
            img = image_source
            
        if img is None:
            return None
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Try multiple QR code detection methods
        # Method 1: Using pyzbar
        try:
            from pyzbar.pyzbar import decode
            decoded_objects = decode(gray)
            if decoded_objects:
                for obj in decoded_objects:
                    data = obj.data.decode('utf-8')
                    if validate_qr_data(data):
                        result = parse_qr_data(data)
                        if result:
                            # Check if QR code is already used or expired
                            if is_qr_used(result['name'], result['timestamp']):
                                result['is_used'] = True
                                result['error'] = 'This QR code has already been used or has expired. Please generate a new one.'
                            return result
        except Exception as e:
            app.logger.warning(f"Pyzbar QR detection failed: {str(e)}")
        
        # Method 2: Using OpenCV's QR code detector
        try:
            qr_detector = cv2.QRCodeDetector()
            retval, decoded_info, points, straight_qrcode = qr_detector.detectAndDecodeMulti(gray)
            if retval:
                for data in decoded_info:
                    if data and validate_qr_data(data):
                        result = parse_qr_data(data)
                        if result:
                            # Check if QR code is already used or expired
                            if is_qr_used(result['name'], result['timestamp']):
                                result['is_used'] = True
                                result['error'] = 'This QR code has already been used or has expired. Please generate a new one.'
                            return result
        except Exception as e:
            app.logger.warning(f"OpenCV QR detection failed: {str(e)}")
        
        return None
        
    except Exception as e:
        app.logger.error(f"Error in process_qr_code: {str(e)}")
        return None

def validate_qr_data(data):
    """Validate QR code data format"""
    try:
        parts = data.split(',')
        if len(parts) != 4:  # username,amount,pin,timestamp
            return False
            
        username, amount, pin, timestamp = parts
        
        # Validate username exists
        if username not in users:
            return False
            
        # Validate amount is positive number
        try:
            amount = float(amount)
            if amount <= 0:
                return False
        except ValueError:
            return False
            
        # Validate PIN is numeric
        if not pin.isdigit():
            return False
            
        # Validate timestamp format
        try:
            datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        except ValueError:
            return False
            
        return True
        
    except Exception as e:
        app.logger.error(f"Error validating QR data: {str(e)}")
        return False

def is_qr_used(username, timestamp):
    """Check if a QR code has already been used by comparing with transaction history"""
    try:
        # Convert QR code timestamp to datetime object
        qr_time = datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        
        # Check user's transaction history
        if username in user_history:
            for transaction in user_history[username]:
                # Convert transaction date to datetime object
                trans_time = datetime.strptime(transaction['date'], '%Y-%m-%d %H:%M:%S')
                
                # If transaction time is within 1 second of QR code time, consider it used
                if abs((trans_time - qr_time).total_seconds()) < 1:
                    return True
                
                # Also check if QR code is expired (5 minutes validity)
                if (datetime.now() - qr_time).total_seconds() > 300:  # 5 minutes
                    return True
        
        return False
    except Exception as e:
        app.logger.error(f"Error checking QR usage: {str(e)}")
        return False

def parse_qr_data(data):
    """Parse QR code data into a dictionary"""
    try:
        username, amount, pin, timestamp = data.split(',')
        return {
            'name': username,
            'amount': float(amount),
            'pin': pin,
            'timestamp': timestamp
        }
    except Exception as e:
        app.logger.error(f"Error parsing QR data: {str(e)}")
        return None

@app.route('/confirm')
def confirm():
    name = request.args.get('name', '')
    amount = request.args.get('amount', 0)
    pin = request.args.get('pin', '')
    
    return render_template('confirm.html', name=name, amount=amount, pin=pin)

@app.route('/process', methods=['POST'])
def process():
    global atm_balance  # Move global declaration to the start of the function
    
    name = request.form.get('name', '')
    amount = float(request.form.get('amount', 0))
    pin = request.form.get('pin', '')
    entered_pin = request.form.get('entered_pin', '')
    
    # Validate PIN
    if pin == entered_pin:
        # Check if user exists and has sufficient balance
        if name in users:
            # Check if ATM has sufficient balance
            if atm_balance < amount:
                return render_template('confirm.html', 
                                    name=name, 
                                    amount=amount, 
                                    pin=pin, 
                                    error="ATM has insufficient balance. Please try a lower amount.")
            
            # Check if user has sufficient balance
            if users[name]['balance'] >= amount:
                # Create transaction record
                transaction = {
                    'id': len(atm_history) + 1,
                    'name': name,
                    'amount': amount,
                    'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'status': 'Completed',
                    'type': 'ATM'
                }
                
                # Add to ATM history
                atm_history.append(transaction)
                
                # Add to user history
                if name not in user_history:
                    user_history[name] = []
                user_history[name].append(transaction)
                
                # Update user balance and ATM balance
                users[name]['balance'] -= amount
                atm_balance -= amount  # Decrease ATM balance when user withdraws
                
                # Save data after successful transaction
                save_data()
                
                # Store transaction in session for success page
                session['last_transaction'] = transaction
                return redirect(url_for('success'))
            else:
                return render_template('confirm.html', 
                                    name=name, 
                                    amount=amount, 
                                    pin=pin, 
                                    error="Insufficient balance. Please try a lower amount.")
        else:
            return render_template('confirm.html', 
                                name=name, 
                                amount=amount, 
                                pin=pin, 
                                error="User not found.")
    else:
        return render_template('confirm.html', 
                            name=name, 
                            amount=amount, 
                            pin=pin, 
                            error="Invalid PIN. Please try again.")

@app.route('/success')
def success():
    transaction = session.get('last_transaction', None)
    if not transaction:
        return redirect(url_for('scan'))
    
    return render_template('success.html', transaction=transaction)

@app.route('/history')
@user_required
def history():
    username = session.get('username')
    user_role = users[username]['role'] if username in users else None
    
    if user_role == 'admin':
        # Admin sees ATM history
        return render_template('history.html', 
                             transactions=atm_history,
                             is_admin=True,
                             username=username)
    else:
        # Regular users see only their transactions
        user_transactions = user_history.get(username, [])
        return render_template('history.html', 
                             transactions=user_transactions,
                             is_admin=False,
                             username=username)

@app.route('/generate', methods=['GET', 'POST'])
@user_required
def generate():
    if request.method == 'POST':
        username = session.get('username')
        amount = request.form.get('amount')
        pin = request.form.get('pin')
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')  # Add timestamp
        
        # Create QR code data with timestamp
        qr_data = f"{username},{amount},{pin},{timestamp}"  # Include timestamp in QR data
        logger.debug(f"Generating QR code with data: {qr_data}")
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        # Create QR code image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code to BytesIO object
        img_io = BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        # Save QR code to file with timestamp in filename
        filename = f"qr_{username}_{timestamp}.png"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        img.save(filepath)
        
        return render_template('generate.html', 
                             qr_code=url_for('static', filename=f'uploads/{filename}'),
                             username=username,
                             amount=amount,
                             timestamp=timestamp)
    
    return render_template('generate.html', username=session.get('username'))

@app.route('/dashboard')
@user_required
def dashboard():
    username = session.get('username')
    user_data = users[username]
    user_role = user_data['role']
    
    if user_role == 'admin':
        # For admin, show ATM balance and recent ATM transactions
        recent_transactions = atm_history[-5:] if atm_history else []
        return render_template('dashboard.html',
                             username=username,
                             is_admin=True,
                             atm_balance=atm_balance,
                             transactions=recent_transactions)
    else:
        # For regular users, show their balance and recent transactions
        user_transactions = user_history.get(username, [])[-5:] if username in user_history else []
        return render_template('dashboard.html',
                             username=username,
                             is_admin=False,
                             balance=user_data['balance'],
                             transactions=user_transactions)

@app.route('/export/<format>')
@admin_required
def export_data(format):
    if format not in ['csv', 'json']:
        return "Invalid format", 400
        
    # Prepare data for export
    export_data = {
        'users': {
            username: {
                'role': data['role'],
                'balance': data['balance']
            } for username, data in users.items()
        },
        'atm_balance': atm_balance,
        'atm_history': atm_history,
        'user_history': user_history,
        'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    if format == 'json':
        # Create JSON file
        json_data = json.dumps(export_data, indent=4)
        mem_file = io.BytesIO()
        mem_file.write(json_data.encode('utf-8'))
        mem_file.seek(0)
        return send_file(
            mem_file,
            mimetype='application/json',
            as_attachment=True,
            download_name=f'qratm_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )
    else:
        # Create CSV files
        mem_file = io.BytesIO()
        writer = csv.writer(mem_file)
        
        # Write users data
        writer.writerow(['Users Data'])
        writer.writerow(['Username', 'Role', 'Balance'])
        for username, data in users.items():
            writer.writerow([username, data['role'], data['balance']])
        
        writer.writerow([])  # Empty row for separation
        
        # Write ATM balance
        writer.writerow(['ATM Balance'])
        writer.writerow([atm_balance])
        
        writer.writerow([])  # Empty row for separation
        
        # Write ATM history
        writer.writerow(['ATM History'])
        writer.writerow(['ID', 'User', 'Amount', 'Date', 'Status', 'Type'])
        for t in atm_history:
            writer.writerow([
                t['id'],
                t['name'],
                t['amount'],
                t['date'],
                t['status'],
                t['type']
            ])
        
        writer.writerow([])  # Empty row for separation
        
        # Write user history
        writer.writerow(['User History'])
        for username, transactions in user_history.items():
            writer.writerow([username])
            for t in transactions:
                writer.writerow([
                    t['id'],
                    t['name'],
                    t['amount'],
                    t['date'],
                    t['status'],
                    t['type']
                ])
        
        mem_file.seek(0)
        return send_file(
            mem_file,
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'qratm_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

# Add a route to manually save data (admin only)
@app.route('/save_data')
@admin_required
def manual_save():
    save_data()
    flash('Data saved successfully', 'success')
    return redirect(url_for('dashboard'))

@app.route('/deposit', methods=['POST'])
@admin_required
def deposit():
    try:
        user_id = request.form.get('user_id')
        amount = float(request.form.get('amount', 0))
        
        # Validate user exists
        if user_id not in users:
            flash('User not found', 'danger')
            return redirect(url_for('dashboard'))
            
        # Validate amount is positive
        if amount <= 0:
            flash('Amount must be greater than 0', 'danger')
            return redirect(url_for('dashboard'))
            
        # Create transaction record
        transaction = {
            'id': len(atm_history) + 1,
            'name': user_id,
            'amount': amount,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': 'Completed',
            'type': 'Deposit'
        }
        
        # Add to ATM history
        atm_history.append(transaction)
        
        # Add to user history
        if user_id not in user_history:
            user_history[user_id] = []
        user_history[user_id].append(transaction)
        
        # Update user balance and ATM balance
        users[user_id]['balance'] += amount
        global atm_balance
        atm_balance += amount
        
        # Save data after successful transaction
        save_data()
        
        flash(f'Successfully deposited ${amount:.2f} to {user_id}\'s account', 'success')
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        app.logger.error(f"Error processing deposit: {str(e)}")
        flash('An error occurred while processing the deposit', 'danger')
        return redirect(url_for('dashboard'))

# Error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Create SSL context
    ssl_context = ('cert.pem', 'key.pem')
    app.run(host='0.0.0.0', port=5000, ssl_context=ssl_context, debug=True)
