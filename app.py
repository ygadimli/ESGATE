from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
from flask_cors import CORS
import google.generativeai as genai
from google.generativeai import types
import json
import sqlite3
import bcrypt
import jwt
import datetime
from functools import wraps
import traceback
import gc
import random

# ========================== Flask Setup ==========================
app = Flask(__name__)
CORS(app)
app.config['SECRET_KEY'] = "ESGATE_SECRET_KEY_2025_SECURE"

# Gemini API konfiqurasiyası
GEMINI_API_KEY = "AIzaSyAwqnBxPVXZaxYsGQEmEq2FqnJUbgMkq78"
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-2.0-flash')

# News prompts for AI
news_prompts = [
    "Find one recent, important news story about the EU's Corporate Sustainability Reporting Directive (CSRD) scope changes for SMEs.",
    "What is the most recent news regarding the EU's Omnibus package and its effect on ESG compliance for European SMEs?",
    "Detail a recent, major news story on how new EU ESG regulations are altering the supply chain relationship between large European corporations and Azerbaijani SMEs.",
    "Report one recent, significant development concerning the simplification of EU ESG rules and the impact on small and medium-sized enterprises (SMEs) in Europe.",
    "Find one recent, major news story about government support or subsidy programs for European SMEs to help with new ESG compliance burdens.",
]

# ========================== Database Setup ==========================
def init_db():
    # Users database
    user_conn = sqlite3.connect('users.db')
    user_cursor = user_conn.cursor()
    user_cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password BLOB NOT NULL,
            role TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    user_conn.commit()
    user_conn.close()
    
    # Predictions/Data database
    data_conn = sqlite3.connect('data.db')
    data_cursor = data_conn.cursor()
    
    # Predictions table - for historical tracking
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_name TEXT,
            category TEXT,
            int_rate REAL,
            default_rate REAL,
            sus_score REAL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')
    
    # Company ESG data
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS company_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            esg_score REAL,
            environmental_score REAL,
            social_score REAL,
            governance_score REAL,
            eu_compliance TEXT,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids expense tracking
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT,
            amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids goals
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            allowance REAL,
            goal_name TEXT,
            goal_amount REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids progress tracking
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            badges_count INTEGER DEFAULT 0,
            lessons_completed INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            ethical_score INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids badges earned
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids lessons completed
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            lesson_id TEXT NOT NULL,
            lesson_name TEXT,
            xp_earned INTEGER DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Kids tasks completed
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS kids_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            task_name TEXT,
            company_name TEXT,
            badge_earned TEXT,
            xp_earned INTEGER DEFAULT 0,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Chat history for all users
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT,
            chat_type TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Business simulator state for kids
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS business_simulator (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            balance REAL DEFAULT 100,
            items_sold INTEGER DEFAULT 0,
            ethical_score INTEGER DEFAULT 50,
            day INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Talent tasks posted by companies for kids
    data_cursor.execute('''
        CREATE TABLE IF NOT EXISTS talent_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            company_name TEXT,
            title TEXT NOT NULL,
            description TEXT,
            duration TEXT,
            badge_name TEXT,
            xp_reward INTEGER DEFAULT 30,
            learning_outcome TEXT,
            completions INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    data_conn.commit()
    data_conn.close()

init_db()

# ========================== Helper Functions ==========================
def esgatescoref(int_rate, default_rate, sus_score):
    """ESGate score calculation formula"""
    sustainability_component = (sus_score + 0.1) * 10    
    default_risk_component = (1 - default_rate) * 100
    MAX_ACCEPTABLE_RATE = 0.7
    normalized_rate = min(max(int_rate, 0.0), MAX_ACCEPTABLE_RATE) 
    interest_rate_component = (1 - (normalized_rate / MAX_ACCEPTABLE_RATE)) * 100
    WEIGHT_SUS = 0.31
    WEIGHT_DEF = 0.41
    WEIGHT_INT = 0.31
    
    final_score = (sustainability_component * WEIGHT_SUS) + \
                  (default_risk_component * WEIGHT_DEF) + \
                  (interest_rate_component * WEIGHT_INT)
                  
    return min(int(final_score), 100)

def get_esg_tier(esg_score):
    """Get ESG tier based on score"""
    if esg_score <= 30:
        return "Rank I", "I"
    elif 30 < esg_score <= 55:
        return "Rank II", "II"
    elif 55 < esg_score <= 70:
        return "Rank III", "III"
    elif 70 < esg_score <= 90:
        return "Rank IV", "IV"
    else:
        return "Rank V", "V"

def get_esg_data(user_id):
    """Get latest ESG data for a user"""
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT int_rate, default_rate, sus_score, created_at
            FROM predictions
            WHERE user_id=?
            ORDER BY created_at DESC
            LIMIT 2
        ''', (user_id,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {
                'esg_score': 0,
                'int_rate': None,
                'default_rate': None,
                'sus_score': None,
                'esg_improvement': 0,
                'has_data': False
            }
        
        latest = rows[0]
        int_rate = latest[0]
        default_rate = latest[1]
        sus_score = latest[2]

        if int_rate is not None and default_rate is not None and sus_score is not None:
            current_esg_score = esgatescoref(int_rate, default_rate, sus_score)
        else:
            current_esg_score = 0
            
        esg_improvement = 0
        if len(rows) > 1:
            previous = rows[1]
            prev_int_rate = previous[0]
            prev_def_rate = previous[1]
            prev_sus_rate = previous[2]

            if prev_int_rate is not None and prev_def_rate is not None and prev_sus_rate is not None:
                previous_esg_score = esgatescoref(prev_int_rate, prev_def_rate, prev_sus_rate)
                esg_improvement = current_esg_score - previous_esg_score
                
        return {
            'esg_score': current_esg_score,
            'int_rate': int_rate,
            'default_rate': default_rate,
            'sus_score': sus_score,
            'esg_improvement': esg_improvement,
            'has_data': True
        }
    except Exception as e:
        print(f"Error fetching ESG data: {e}")
        return {
            'esg_score': 0,
            'int_rate': None,
            'default_rate': None,
            'sus_score': None,
            'esg_improvement': 0,
            'has_data': False
        }

def calculate_progress_percent(esg_score, target_score=80):
    if esg_score >= target_score:
        return 100
    return int((esg_score / target_score) * 100)

def get_user_details(user_id):
    """Fetches user's company category and username"""
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT category, username FROM users WHERE id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return row[0] or "Unspecified", row[1]
    return "Unspecified", "User"

def save_prediction_metric(user_id, company_name, category, metric_name, metric_value):
    """Saves a single prediction metric"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    company_name_lower = str(company_name).lower().strip() if company_name else ''

    if metric_name not in ['int_rate', 'default_rate', 'sus_score']:
        conn.close()
        raise ValueError("Invalid metric_name provided.")

    try:
        cursor.execute("""
            SELECT id FROM predictions
            WHERE user_id = ? AND lower(company_name) = ? AND created_at >= datetime('now', '-5 minutes')
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id, company_name_lower))
        recent_record = cursor.fetchone()

        if recent_record:
            record_id = recent_record[0]
            query = f"UPDATE predictions SET {metric_name} = ? WHERE id = ?"
            cursor.execute(query, (metric_value, record_id))
        else:
            query = f"INSERT INTO predictions (user_id, company_name, category, {metric_name}) VALUES (?, ?, ?, ?)"
            cursor.execute(query, (user_id, company_name_lower, category, metric_value))

        conn.commit()
    except sqlite3.Error as e:
        print(f"DATABASE ERROR during save: {e}")
        conn.rollback()
    finally:
        conn.close()
        gc.collect()

def calculate_percentage_change(old_value, new_value):
    if old_value is None or new_value is None:
        return None
    if old_value == 0:
        return float('inf') if new_value > 0 else float('-inf') if new_value < 0 else 0.0
    try:
        return ((new_value - old_value) / abs(old_value)) * 100
    except Exception:
        return None

# ========================== Demo Data ==========================
COMPANIES_DATA = [
    {
        "id": 1,
        "name": "AzərEnerji Plus",
        "sector": "Enerji",
        "esg_score": 72,
        "environmental": 68,
        "social": 75,
        "governance": 73,
        "roi_potential": 15.2,
        "market_cap": "45M AZN",
        "growth_rate": 12.5,
        "description": "Bərpa olunan enerji həlləri təqdim edən şirkət"
    },
    {
        "id": 2,
        "name": "GreenBuild Azerbaijan",
        "sector": "Tikinti",
        "esg_score": 65,
        "environmental": 70,
        "social": 62,
        "governance": 63,
        "roi_potential": 11.8,
        "market_cap": "28M AZN",
        "growth_rate": 8.3,
        "description": "Ekoloji tikinti materialları istehsalçısı"
    },
    {
        "id": 3,
        "name": "AgriTech Baku",
        "sector": "Kənd təsərrüfatı",
        "esg_score": 78,
        "environmental": 82,
        "social": 76,
        "governance": 76,
        "roi_potential": 18.5,
        "market_cap": "35M AZN",
        "growth_rate": 22.1,
        "description": "Smart kənd təsərrüfatı texnologiyaları"
    },
    {
        "id": 4,
        "name": "EcoTextile Group",
        "sector": "Tekstil",
        "esg_score": 58,
        "environmental": 55,
        "social": 60,
        "governance": 59,
        "roi_potential": 9.2,
        "market_cap": "18M AZN",
        "growth_rate": 5.7,
        "description": "Davamlı moda və tekstil istehsalı"
    },
    {
        "id": 5,
        "name": "CleanWater Solutions",
        "sector": "Su təchizatı",
        "esg_score": 85,
        "environmental": 90,
        "social": 82,
        "governance": 83,
        "roi_potential": 21.3,
        "market_cap": "52M AZN",
        "growth_rate": 28.4,
        "description": "Su təmizləmə və idarəetmə sistemləri"
    }
]

# ========================== Auth Decorator ==========================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        if 'token' in request.cookies:
            token = request.cookies.get('token')
        
        if not token:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                token = auth_header.split(" ")[1]
        
        if not token:
            if request.is_json or request.path.startswith('/api/'):
                return jsonify({"message": "Token tələb olunur!"}), 401
            return redirect(url_for('login_page'))
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = data['sub']
            role = data['role']
            user_id = data['id']
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token vaxtı bitib!"}), 401
        except Exception as e:
            return jsonify({"message": f"Token xətası: {str(e)}"}), 401
        
        return f(current_user, role, user_id, *args, **kwargs)
    return decorated

# ========================== Page Routes ==========================
@app.route('/')
def index():
    # Check if user is already logged in
    token = request.cookies.get('token')
    if token:
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            role = data.get('role')
            if role == 'investor':
                return redirect(url_for('investor'))
            elif role == 'enterprise':
                return redirect(url_for('company'))
            elif role == 'kids':
                return redirect(url_for('kids'))
        except:
            pass
    # Redirect non-logged-in users to login page
    return redirect(url_for('login_page'))

@app.route('/home')
def home_page():
    """Landing page for marketing purposes"""
    # Check if user is logged in
    token = request.cookies.get('token')
    user_data = None
    
    if token:
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            user_data = {
                'username': data.get('sub'),
                'role': data.get('role'),
                'logged_in': True
            }
        except:
            pass
    
    return render_template('index.html', user=user_data)

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/signup')
def signup_page():
    return render_template('signup.html')

@app.route('/dashboard')
@token_required
def dashboard(current_user, role, user_id):
    if role == 'investor':
        return redirect(url_for('investor'))
    elif role == 'enterprise':
        return redirect(url_for('company'))
    elif role == 'kids':
        return redirect(url_for('kids'))
    return redirect(url_for('index'))

@app.route('/company')
@token_required
def company(current_user, role, user_id):
    if role != 'enterprise':
        return redirect(url_for('dashboard'))
    
    esg_data = get_esg_data(user_id)
    user_category, _ = get_user_details(user_id)
    
    return render_template('company.html', 
                         username=current_user,
                         esg_score=esg_data['esg_score'],
                         has_data=esg_data['has_data'],
                         category=user_category)

@app.route('/analysis')
@token_required
def analysis(current_user, role, user_id):
    if role != 'enterprise':
        return redirect(url_for('dashboard'))
    
    esg_data = get_esg_data(user_id)
    user_category, _ = get_user_details(user_id)
    
    return render_template('analysis.html',
                         company_name=current_user.capitalize(),
                         username=current_user,
                         esg_score=esg_data['esg_score'],
                         has_data=esg_data['has_data'],
                         category=user_category)

@app.route('/investor')
@token_required
def investor(current_user, role, user_id):
    if role != 'investor':
        return redirect(url_for('dashboard'))
    return render_template('investor.html', username=current_user)

@app.route('/kids')
@token_required
def kids(current_user, role, user_id):
    if role != 'kids':
        return redirect(url_for('dashboard'))
    
    # Get or create kids progress
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM kids_progress WHERE user_id = ?', (user_id,))
    progress = cursor.fetchone()
    
    if not progress:
        # Create initial progress
        cursor.execute('''
            INSERT INTO kids_progress (user_id, xp, level, badges_count, lessons_completed, tasks_completed, ethical_score)
            VALUES (?, 0, 1, 0, 0, 0, 50)
        ''', (user_id,))
        conn.commit()
        progress = (None, user_id, 0, 1, 0, 0, 0, 50, None, None)
    
    # Get or create business simulator state
    cursor.execute('SELECT * FROM business_simulator WHERE user_id = ?', (user_id,))
    simulator = cursor.fetchone()
    
    if not simulator:
        cursor.execute('''
            INSERT INTO business_simulator (user_id, balance, items_sold, ethical_score, day)
            VALUES (?, 100, 0, 50, 1)
        ''', (user_id,))
        conn.commit()
        simulator = (None, user_id, 100, 0, 50, 1, None)
    
    conn.close()
    
    # progress: id, user_id, xp, level, badges_count, lessons_completed, tasks_completed, ethical_score
    # simulator: id, user_id, balance, items_sold, ethical_score, day
    
    return render_template('kids.html', 
                         username=current_user,
                         xp=progress[2],
                         level=progress[3],
                         badges_count=progress[4],
                         lessons_completed=progress[5],
                         tasks_completed=progress[6],
                         ethical_score=progress[7],
                         sim_balance=simulator[2],
                         sim_sold=simulator[3],
                         sim_ethical=simulator[4],
                         sim_day=simulator[5])

# ========================== Auth API ==========================
@app.route('/api/signup', methods=['POST'])
def api_signup():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'enterprise')
    category = data.get('category', '')
    
    if not username or not password:
        return jsonify({"message": "İstifadəçi adı və şifrə tələb olunur"}), 400
    
    if len(password) < 4:
        return jsonify({"message": "Şifrə ən azı 4 simvol olmalıdır"}), 400
    
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"message": "Bu istifadəçi adı artıq mövcuddur"}), 400
        
        cursor.execute(
            "INSERT INTO users (username, password, role, category) VALUES (?, ?, ?, ?)",
            (username, hashed_password, role, category)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Qeydiyyat uğurlu oldu!"}), 200
    except Exception as e:
        return jsonify({"message": f"Xəta: {str(e)}"}), 500

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    remember = data.get('remember', False)
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password, role FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            user_id, stored_hash, role = result
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                token_duration = datetime.timedelta(days=15) if remember else datetime.timedelta(hours=24)
                
                payload = {
                    'sub': username,
                    'role': role,
                    'id': user_id,
                    'iat': datetime.datetime.now(datetime.UTC),
                    'exp': datetime.datetime.now(datetime.UTC) + token_duration
                }
                
                token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
                
                response = make_response(jsonify({
                    "message": "Giriş uğurlu!",
                    "token": token,
                    "role": role
                }))
                
                response.set_cookie(
                    'token',
                    token,
                    httponly=True,
                    secure=False,
                    path='/',
                    max_age=int(token_duration.total_seconds())
                )
                
                return response, 200
        
        return jsonify({"message": "Yanlış istifadəçi adı və ya şifrə"}), 401
    except Exception as e:
        return jsonify({"message": f"Xəta: {str(e)}"}), 500

@app.route('/api/logout', methods=['POST'])
def api_logout():
    response = make_response(jsonify({"message": "Çıxış uğurlu!"}))
    response.set_cookie('token', '', expires=0, path='/')
    return response, 200

# ========================== Prediction APIs ==========================
@app.route('/predict_int_rate', methods=['POST'])
@token_required
def predict_int_rate(current_user, role, user_id):
    """Interest rate prediction - simplified version"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data received"}), 400
    
    # Simplified calculation based on input parameters
    try:
        revenue = float(data.get('revenue', 100000))
        loan_amt = float(data.get('loan_amt', 50000))
        operation_years = float(data.get('operation_years', 5))
        default_hist = int(data.get('default_hist', 0))
        
        # Simple formula for demo
        base_rate = 0.08
        loan_factor = min(loan_amt / revenue, 1) * 0.05
        years_factor = max(0, (10 - operation_years) / 100)
        default_factor = default_hist * 0.02
        
        int_rate = base_rate + loan_factor + years_factor + default_factor
        int_rate = max(0.03, min(0.25, int_rate))  # Clamp between 3% and 25%
        
        # Save to database
        user_category, _ = get_user_details(user_id)
        save_prediction_metric(user_id, current_user, user_category, 'int_rate', float(int_rate))
        
        return jsonify({'int_rate': float(int_rate)}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

@app.route('/predict_default', methods=['POST'])
@token_required
def predict_default(current_user, role, user_id):
    """Default rate prediction - simplified version"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON data received"}), 400
    
    try:
        annual_income = float(data.get('Annual Income', 100000))
        credit_score = float(data.get('Credit Score', 700))
        current_loan = float(data.get('Current Loan Amount', 50000))
        
        # Simple formula for demo
        base_rate = 0.15
        income_factor = max(0, (200000 - annual_income) / 2000000)
        credit_factor = max(0, (800 - credit_score) / 1000)
        loan_factor = min(current_loan / annual_income, 1) * 0.1
        
        default_rate = base_rate + income_factor + credit_factor + loan_factor
        default_rate = max(0.02, min(0.50, default_rate))  # Clamp between 2% and 50%
        
        # Save to database
        user_category, _ = get_user_details(user_id)
        save_prediction_metric(user_id, current_user, user_category, 'default_rate', float(default_rate))
        
        return jsonify({'default_rate': float(default_rate)}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Prediction failed: {str(e)}"}), 500

@app.route('/sustainability_prediction', methods=['POST'])
@token_required
def sustainability_prediction(current_user, role, user_id):
    """Sustainability score prediction using Gemini"""
    metrics_dict = request.get_json()
    if not metrics_dict:
        return jsonify({"error": "Missing or invalid JSON body"}), 400

    sector_averages = {
        'energy_efficiency': 4.5,
        'carbon_intensity': 1.0,
        'water_usage': 3500
    }

    prompt = f"""
    Sən ESG ekspert analitikisən. Şirkətin davamlılığını qiymətləndir:

    Şirkətin Məlumatları:
    - Enerji Səmərəliliyi: {metrics_dict.get('energy_efficiency')} MWh/vahid
    - Karbon İntensivliyi: {metrics_dict.get('carbon_intensity')} tCO2e/vahid
    - Su İstehlakı: {metrics_dict.get('water_usage')} Litr/vahid

    Sektor Ortalamaları:
    - Enerji Səmərəliliyi: {sector_averages['energy_efficiency']} MWh/vahid
    - Karbon İntensivliyi: {sector_averages['carbon_intensity']} tCO2e/vahid
    - Su İstehlakı: {sector_averages['water_usage']} Litr/vahid

    Cavabını YALNIZ Azərbaycan dilində, JSON formatında ver:
    {{
        "sus_score": <float 0-10>,
        "summary": "<qısa xülasə - Azərbaycan dilində>",
        "strengths": ["<güclü tərəf - Azərbaycan dilində>"],
        "weaknesses": ["<zəif tərəf - Azərbaycan dilində>"],
        "recommendations": ["<tövsiyə - Azərbaycan dilində>"]
    }}
    
    Yalnız JSON cavab ver, əlavə mətn olmasın.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        parsed_result = json.loads(result.strip())
        
        # Save to database
        score_to_save = float(parsed_result.get('sus_score', 5))
        user_category, _ = get_user_details(user_id)
        save_prediction_metric(user_id, current_user, user_category, 'sus_score', score_to_save)
        
        return jsonify(parsed_result)
    except Exception as e:
        print(f"Gemini Error: {e}")
        # Fallback response - Azərbaycan dilində
        fallback = {
            "sus_score": 5.0,
            "summary": "AI analizi hazırda mövcud deyil.",
            "strengths": ["Məlumatlar qəbul edildi"],
            "weaknesses": ["AI xidməti hazırda mövcud deyil"],
            "recommendations": ["Bir az sonra yenidən cəhd edin"]
        }
        return jsonify(fallback)

@app.route('/company_summary', methods=['POST'])
@token_required
def company_summary(current_user, role, user_id):
    """Get AI summary for company metrics"""
    data = request.get_json()
    int_rate = data.get('int_rate')
    def_rate = data.get('default_rate')
    sus_score = data.get('sus_score')
    
    try:
        esgatescore = esgatescoref(int_rate, def_rate, sus_score)
    except:
        esgatescore = None

    int_rate_percent = f"{int_rate * 100:.2f}%" if int_rate else "N/A"
    default_rate_percent = f"{def_rate * 100:.2f}%" if def_rate else "N/A"

    prompt = f"""
    Sən maliyyə və ESG məsləhətçisi AI-sən. Şirkətin aşağıdakı metrikləri var:

    Ümumi ESGate Skoru: {esgatescore}/100
    Faiz Dərəcəsi: {int_rate_percent}
    Defolt Ehtimalı: {default_rate_percent}
    Davamlılıq Skoru: {sus_score}/10

    Cavabını YALNIZ Azərbaycan dilində ver:
    1. Qısa xülasə (2-3 cümlə)
    2. Risk səviyyəsi: Aşağı (<30%), Orta (30-45%), Yüksək (>50%)
    3. Güclü və zəif tərəflər
    4. 2-3 praktiki tövsiyə

    Yalnız JSON formatında cavab ver:
    {{
        "summary": "... (Azərbaycan dilində)",
        "strengths": ["... (Azərbaycan dilində)"],
        "weaknesses": ["... (Azərbaycan dilində)"],
        "recommendations": ["... (Azərbaycan dilində)"]
    }}
    
    Yalnız JSON cavab ver, əlavə mətn olmasın.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        summary_result = json.loads(result.strip())
        return jsonify({"mistral_summary": summary_result, "esgatescore": esgatescore}), 200
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "AI analysis unavailable", "esgatescore": esgatescore}), 200

# ========================== History API ==========================
@app.route('/history', methods=['POST'])
@token_required
def history(current_user, role, user_id):
    """Get historical prediction data"""
    company_name = current_user

    try:
        conn = sqlite3.connect('data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Query by user_id only - simpler and more reliable
        cursor.execute('''
            SELECT id, int_rate, default_rate, sus_score, created_at
            FROM predictions
            WHERE user_id = ? AND int_rate IS NOT NULL AND default_rate IS NOT NULL AND sus_score IS NOT NULL
            ORDER BY created_at DESC
        ''', (user_id,))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return jsonify({"message": "Tarixçə tapılmadı. Əvvəlcə analiz edin.", "history": []}), 200

        history_data = [dict(row) for row in rows]
        improvements = {}
        ai_analysis = {}

        if len(history_data) >= 2:
            first = history_data[-1]  # Ən köhnə
            last = history_data[0]    # Ən yeni

            improvements['int_rate_change'] = calculate_percentage_change(
                first['int_rate'], last['int_rate'])
            improvements['default_rate_change'] = calculate_percentage_change(
                first['default_rate'], last['default_rate'])
            improvements['sus_score_change'] = calculate_percentage_change(
                first['sus_score'], last['sus_score'])
            
            # AI Analysis of trends - Azərbaycan dilində
            prompt = f"""
            Sən maliyyə və ESG analitikisən. '{company_name}' şirkəti üçün tarixi trendləri analiz et.
            
            Dəyişikliklər:
            - Faiz Dərəcəsi: {improvements['int_rate_change']:.1f}% dəyişib (azalma yaxşıdır)
            - Defolt Dərəcəsi: {improvements['default_rate_change']:.1f}% dəyişib (azalma yaxşıdır)
            - Davamlılıq Skoru: {improvements['sus_score_change']:.1f}% dəyişib (artım yaxşıdır)
            
            Cavabını YALNIZ Azərbaycan dilində, JSON formatında ver:
            {{
                "interest_rate_comment": "Faiz dərəcəsi haqqında qısa şərh (Azərbaycan dilində)",
                "default_rate_comment": "Defolt dərəcəsi haqqında qısa şərh (Azərbaycan dilində)",
                "sus_score_comment": "Davamlılıq skoru haqqında qısa şərh (Azərbaycan dilində)",
                "overall_summary": "Ümumi xülasə (Azərbaycan dilində, 2-3 cümlə)"
            }}
            
            Yalnız JSON cavab ver, əlavə mətn olmasın.
            """
            
            try:
                response = model.generate_content(prompt)
                result = response.text.strip()
                if result.startswith('```json'):
                    result = result[7:]
                if result.startswith('```'):
                    result = result[3:]
                if result.endswith('```'):
                    result = result[:-3]
                ai_analysis = json.loads(result.strip())
            except Exception as e:
                print(f"AI Analysis Error: {e}")
                ai_analysis = {"error": "AI analizi hazırda mövcud deyil"}
        else:
            improvements['message'] = "Dəyişiklik hesablamaq üçün ən azı 2 məlumat nöqtəsi lazımdır."
            ai_analysis['message'] = "AI analizi üçün ən azı 2 məlumat nöqtəsi lazımdır."

        return jsonify({
            "company_name": company_name,
            "history": history_data,
            "improvement_metrics": improvements,
            "ai_analysis": ai_analysis
        }), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/compare-history', methods=['POST'])
@token_required
def compare_history(current_user, role, user_id):
    """Compare two specific historical data points"""
    data = request.get_json()
    first_id = data.get('first_id')
    second_id = data.get('second_id')
    
    if not first_id or not second_id:
        return jsonify({"error": "İki tarixçə ID-si tələb olunur"}), 400
    
    try:
        conn = sqlite3.connect('data.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get both data points
        cursor.execute('''
            SELECT id, int_rate, default_rate, sus_score, created_at
            FROM predictions
            WHERE user_id = ? AND id IN (?, ?)
        ''', (user_id, first_id, second_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) != 2:
            return jsonify({"error": "Tarixçə tapılmadı"}), 404
        
        # Sort by created_at to determine which is first and which is second
        sorted_rows = sorted(rows, key=lambda x: x['created_at'])
        first = dict(sorted_rows[0])
        second = dict(sorted_rows[1])
        
        # Calculate changes
        improvements = {
            'int_rate_change': calculate_percentage_change(first['int_rate'], second['int_rate']),
            'default_rate_change': calculate_percentage_change(first['default_rate'], second['default_rate']),
            'sus_score_change': calculate_percentage_change(first['sus_score'], second['sus_score'])
        }
        
        # AI Analysis - Azərbaycan dilində
        prompt = f"""
        Sən maliyyə və ESG analitikisən. '{current_user}' şirkəti üçün iki tarixçə nöqtəsini müqayisə et.
        
        İlk Tarixçə ({first['created_at']}):
        - Faiz Dərəcəsi: {first['int_rate']*100:.2f}%
        - Defolt Dərəcəsi: {first['default_rate']*100:.2f}%
        - Davamlılıq Skoru: {first['sus_score']:.2f}/10
        
        İkinci Tarixçə ({second['created_at']}):
        - Faiz Dərəcəsi: {second['int_rate']*100:.2f}%
        - Defolt Dərəcəsi: {second['default_rate']*100:.2f}%
        - Davamlılıq Skoru: {second['sus_score']:.2f}/10
        
        Dəyişikliklər:
        - Faiz Dərəcəsi: {improvements['int_rate_change']:.1f}% (azalma yaxşıdır)
        - Defolt Dərəcəsi: {improvements['default_rate_change']:.1f}% (azalma yaxşıdır)
        - Davamlılıq Skoru: {improvements['sus_score_change']:.1f}% (artım yaxşıdır)
        
        Cavabını YALNIZ Azərbaycan dilində, JSON formatında ver:
        {{
            "interest_rate_comment": "Faiz dərəcəsi dəyişikliyi haqqında şərh (Azərbaycan dilində)",
            "default_rate_comment": "Defolt dərəcəsi dəyişikliyi haqqında şərh (Azərbaycan dilində)",
            "sus_score_comment": "Davamlılıq skoru dəyişikliyi haqqında şərh (Azərbaycan dilində)",
            "overall_summary": "Ümumi müqayisə xülasəsi (Azərbaycan dilində, 3-4 cümlə)"
        }}
        
        Yalnız JSON cavab ver, əlavə mətn olmasın.
        """
        
        try:
            response = model.generate_content(prompt)
            result = response.text.strip()
            if result.startswith('```json'):
                result = result[7:]
            if result.startswith('```'):
                result = result[3:]
            if result.endswith('```'):
                result = result[:-3]
            ai_analysis = json.loads(result.strip())
        except Exception as e:
            print(f"AI Analysis Error: {e}")
            ai_analysis = {"error": "AI analizi hazırda mövcud deyil"}
        
        return jsonify({
            "first": first,
            "second": second,
            "improvements": improvements,
            "ai_analysis": ai_analysis
        }), 200
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

# ========================== Company APIs ==========================
@app.route('/api/calculate-esg', methods=['POST'])
@token_required
def calculate_esg(current_user, role, user_id):
    data = request.json
    
    prompt = f"""
    Sən ESG (Environmental, Social, Governance) ekspertisən. Aşağıdakı şirkət məlumatlarına əsasən ESG skorunu hesabla və Avropa requlasiyalarına (EU Taxonomy, CSRD) uyğunluq analizi ver.
    
    Şirkət məlumatları:
    - Sektor: {data.get('sector', 'Bilinmir')}
    - İşçi sayı: {data.get('employees', 'Bilinmir')}
    - İllik gəlir: {data.get('revenue', 'Bilinmir')} AZN
    - Enerji istehlakı: {data.get('energy', 'Bilinmir')} kWh
    - Tullantı həcmi: {data.get('waste', 'Bilinmir')} ton
    - Sosial proqramlar: {data.get('social_programs', 'Yoxdur')}
    - İdarəetmə strukturu: {data.get('governance', 'Bilinmir')}
    
    Cavabını JSON formatında ver:
    {{
        "overall_score": 0-100 arası rəqəm,
        "environmental_score": 0-100,
        "social_score": 0-100,
        "governance_score": 0-100,
        "eu_compliance": "Yüksək/Orta/Aşağı",
        "recommendations": ["tövsiyə 1", "tövsiyə 2", "tövsiyə 3"],
        "risk_areas": ["risk 1", "risk 2"],
        "summary": "Qısa analiz"
    }}
    
    Yalnız JSON cavab ver, əlavə mətn olmasın.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        parsed = json.loads(result.strip())
        
        # Save to database
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO company_data (user_id, esg_score, environmental_score, social_score, governance_score, eu_compliance)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, parsed.get('overall_score'), parsed.get('environmental_score'), 
              parsed.get('social_score'), parsed.get('governance_score'), parsed.get('eu_compliance')))
        conn.commit()
        conn.close()
        
        return jsonify(parsed)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/optimize-roi', methods=['POST'])
@token_required
def optimize_roi(current_user, role, user_id):
    data = request.json
    
    prompt = f"""
    Sən maliyyə və ESG investisiya ekspertisən. Aşağıdakı parametrlərə əsasən ROI optimallaşdırma təklifləri ver.
    
    Cari vəziyyət:
    - Cari ROI: {data.get('current_roi', 'Bilinmir')}%
    - İnvestisiya büdcəsi: {data.get('budget', 'Bilinmir')} AZN
    - Sektor: {data.get('sector', 'Bilinmir')}
    - ESG fokus sahəsi: {data.get('esg_focus', 'Ümumi')}
    - Risk toleransı: {data.get('risk_tolerance', 'Orta')}
    
    Cavabını JSON formatında ver:
    {{
        "optimized_roi": "%-lə gözlənilən ROI",
        "investment_areas": [
            {{"area": "sahə adı", "allocation": "%-lə", "expected_return": "%-lə"}}
        ],
        "timeline": "ay/il",
        "key_actions": ["əməliyyat 1", "əməliyyat 2", "əməliyyat 3"],
        "risks": ["risk 1", "risk 2"],
        "summary": "Qısa strategiya"
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        return jsonify(json.loads(result.strip()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate-roadmap', methods=['POST'])
@token_required
def generate_roadmap(current_user, role, user_id):
    """Generate EU compliance roadmap for company"""
    # Get company category from DB
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT category FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    sector = result[0] if result and result[0] else 'Ümumi'
    
    prompt = f"""
    Sən ESG transformasiya ekspertisən. {current_user} şirkəti üçün ({sector} sektoru) Avropa requlasiyalarına (EU Taxonomy, CSRD, SFDR) uyğunlaşma yol xəritəsi hazırla.
    
    Cavabını Azərbaycan dilində, HTML formatında ver (sadəcə içərik, html/body teqləri olmadan):
    - Fazaları numbered list ilə göstər
    - Hər fazanın tapşırıqlarını bullet list ilə göstər
    - Ümumi müddət və büdcəni göstər
    - Tövsiyələri ver
    
    Sadə və anlaşılan formatda yaz.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        return jsonify({"roadmap": result})
    except Exception as e:
        return jsonify({"roadmap": """
            <h4>🗺️ ESG Uyğunluq Yol Xəritəsi</h4>
            <ol>
                <li><strong>Faza 1 (1-3 ay):</strong> ESG Qiymətləndirmə
                    <ul>
                        <li>Mövcud vəziyyətin analizi</li>
                        <li>Gap analizi</li>
                    </ul>
                </li>
                <li><strong>Faza 2 (4-6 ay):</strong> Strategiya
                    <ul>
                        <li>ESG siyasətlərinin hazırlanması</li>
                        <li>Hədəflərin müəyyən edilməsi</li>
                    </ul>
                </li>
                <li><strong>Faza 3 (7-12 ay):</strong> Tətbiq
                    <ul>
                        <li>Sistemlərin qurulması</li>
                        <li>Hesabatların hazırlanması</li>
                    </ul>
                </li>
            </ol>
        """})

@app.route('/api/ai-mentor', methods=['POST'])
@token_required
def ai_mentor(current_user, role, user_id):
    """AI Mentor for ESG questions"""
    data = request.json
    question = data.get('question', '')
    
    if not question:
        return jsonify({"error": "Sual daxil edilməyib"}), 400
    
    prompt = f"""
    Sən ESG və davamlılıq üzrə ekspert məsləhətçisən. Azərbaycan dilində cavab ver.
    
    Şirkətin sualı: {question}
    
    Qaydalar:
    1. Qısa və konkret cavab ver (maksimum 150 söz)
    2. Praktiki tövsiyələr ver
    3. Nümunələr ver
    4. Azerbaycan biznes kontekstinə uyğunlaşdır
    
    Cavab ver:
    """
    
    try:
        response = model.generate_content(prompt)
        return jsonify({"answer": response.text.strip()})
    except Exception as e:
        return jsonify({"answer": "Bağışlayın, cavab hazırlanarkən xəta baş verdi. Zəhmət olmasa yenidən cəhd edin."})

@app.route('/api/generate_roi_plan', methods=['POST'])
@token_required
def generate_roi_plan(current_user, role, user_id):
    """Generate ROI optimization plan using Gemini"""
    try:
        data = request.get_json()
        focus = data.get('focus', 'highest_roi')
        
        esg_data = get_esg_data(user_id)
        user_category, _ = get_user_details(user_id)
        
        prompt = f"""
        You are an ESG ROI Optimizer. Generate a 3-point ROI optimization proposal for an SME in the '{user_category}' sector.
        
        Current metrics:
        - ESG Score: {esg_data.get('esg_score', 0)}/100
        - Has Data: {esg_data.get('has_data', False)}
        - Focus Area: {focus}
        
        Return JSON:
        {{
            "has_data": {str(esg_data.get('has_data', False)).lower()},
            "roi_summary": "Overall ROI summary",
            "compliance_risk_assessment": "EU compliance risk assessment",
            "learning_topic": "Recommended learning topic",
            "proposals": [
                {{
                    "title": "Short title",
                    "description": "1-2 sentence description",
                    "predicted_output_graph_value": 25
                }}
            ]
        }}
        """
        
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        return jsonify(json.loads(result.strip())), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "has_data": False,
            "roi_summary": "AI Service unavailable.",
            "compliance_risk_assessment": "Unable to assess at this time.",
            "learning_topic": "ESG Fundamentals",
            "proposals": [
                {"title": "Start Digital Records", "description": "Begin digitizing records for compliance.", "predicted_output_graph_value": 25},
                {"title": "Track Core Metrics", "description": "Monitor energy and waste metrics.", "predicted_output_graph_value": 30},
                {"title": "Document Governance", "description": "Formalize management structure.", "predicted_output_graph_value": 20}
            ]
        }), 500

# ========================== Investor APIs ==========================
@app.route('/api/companies', methods=['GET'])
@token_required
def get_companies(current_user, role, user_id):
    return jsonify(COMPANIES_DATA)

@app.route('/api/companies/discover', methods=['GET'])
@token_required
def discover_companies(current_user, role, user_id):
    """Get all companies for investors to discover"""
    if role != 'investor':
        return jsonify({"message": "Access restricted"}), 403

    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, category FROM users WHERE role = 'enterprise'")
        companies = cursor.fetchall()
        conn.close()

        company_data = []
        pred_conn = sqlite3.connect('data.db')
        pred_cursor = pred_conn.cursor()

        for comp in companies:
            c_id, c_username, c_category = comp
            pred_cursor.execute("""
                SELECT int_rate, default_rate, sus_score 
                FROM predictions 
                WHERE user_id = ? 
                ORDER BY created_at DESC LIMIT 1
            """, (c_id,))
            
            latest = pred_cursor.fetchone()
            score = 0
            defs = 0.0
            ints = 0.0
            
            if latest:
                i_rate, d_rate, s_score = latest
                i_rate = i_rate if i_rate is not None else 0
                d_rate = d_rate if d_rate is not None else 0
                s_score = s_score if s_score is not None else 0
                
                score = esgatescoref(i_rate, d_rate, s_score)
                defs = d_rate
                ints = i_rate

            company_data.append({
                "id": c_id,
                "name": c_username.capitalize(),
                "category": c_category if c_category else "Unspecified",
                "esg_score": score,
                "default_rate": f"{defs*100:.1f}%",
                "int_rate": f"{ints*100:.2f}%",
                "compliance": "CSRD Compliant" if score > 75 else "In Progress"
            })

        pred_conn.close()
        
        # Add demo companies if no real companies exist
        if not company_data:
            company_data = [
                {"id": 1, "name": "Demo Company 1", "category": "Technology", "esg_score": 75, "default_rate": "5.0%", "int_rate": "8.5%", "compliance": "CSRD Compliant"},
                {"id": 2, "name": "Demo Company 2", "category": "Manufacturing", "esg_score": 62, "default_rate": "12.0%", "int_rate": "10.2%", "compliance": "In Progress"}
            ]
        
        return jsonify({"companies": company_data}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/compare-companies', methods=['POST'])
@token_required
def compare_companies(current_user, role, user_id):
    data = request.json
    company_ids = data.get('company_ids', [])
    
    # Try to get companies from database first
    companies = []
    user_conn = sqlite3.connect('users.db')
    user_cursor = user_conn.cursor()
    data_conn = sqlite3.connect('data.db')
    data_cursor = data_conn.cursor()
    
    for cid in company_ids:
        user_cursor.execute("SELECT id, username, category FROM users WHERE id = ?", (cid,))
        user_result = user_cursor.fetchone()
        if user_result:
            data_cursor.execute("""
                SELECT int_rate, default_rate, sus_score FROM predictions 
                WHERE user_id = ? ORDER BY created_at DESC LIMIT 1
            """, (cid,))
            pred = data_cursor.fetchone()
            companies.append({
                "id": user_result[0],
                "name": user_result[1],
                "category": user_result[2] or "Ümumi",
                "int_rate": f"{pred[0]:.2%}" if pred and pred[0] else "N/A",
                "default_rate": f"{pred[1]:.1%}" if pred and pred[1] else "N/A",
                "esg_score": round(pred[2]) if pred and pred[2] else 50
            })
    
    user_conn.close()
    data_conn.close()
    
    # Fallback to COMPANIES_DATA if no DB results
    if not companies:
        companies = [c for c in COMPANIES_DATA if c['id'] in company_ids]
    
    if len(companies) < 2:
        return jsonify({"error": "Müqayisə üçün ən azı 2 şirkət lazımdır"}), 400
    
    prompt = f"""
    Sən investisiya analitikisən. Aşağıdakı şirkətləri ESG və investisiya perspektivindən müqayisə et.
    Cavabını Azərbaycan dilində ver.
    
    Şirkətlər: {json.dumps(companies, ensure_ascii=False)}
    
    Cavabını JSON formatında ver:
    {{
        "comparison_summary": "Ümumi müqayisə (2-3 cümlə)",
        "best_esg": "Ən yaxşı ESG şirkəti və səbəbi",
        "best_investment": "Ən yaxşı investisiya fürsəti və səbəbi",
        "recommendation": "Tövsiyə"
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        analysis = json.loads(result.strip())
        return jsonify(analysis)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/investor/ai-insights', methods=['POST'])
@token_required
def investor_ai_insights(current_user, role, user_id):
    """Generate AI insights for investor portfolio"""
    data = request.json
    portfolio = data.get('portfolio', [])
    
    if not portfolio:
        return jsonify({"error": "Portfolio boşdur. Şirkət əlavə edin."}), 400
    
    prompt = f"""
    Sən professional investisiya məsləhətçisisən. Aşağıdakı portfolioni analiz et və Azərbaycan dilində tövsiyələr ver.
    
    Portfolio: {json.dumps(portfolio, ensure_ascii=False)}
    
    Analiz et:
    1. Portfolio diversifikasiyası
    2. Risk səviyyəsi
    3. ESG performansı
    4. Gəlirlilik potensialı
    
    Cavabını JSON formatında ver:
    {{
        "insights": "Portfolionuz haqqında ətraflı analiz (3-4 cümlə)",
        "risk_level": "Aşağı/Orta/Yüksək",
        "recommendation": "Tövsiyə (1-2 cümlə)",
        "diversification_score": "rəqəm 1-10",
        "next_steps": ["addım 1", "addım 2"]
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        return jsonify(json.loads(result.strip()))
    except Exception as e:
        return jsonify({
            "insights": "Portfolio analizi hazırlandı. " + str(len(portfolio)) + " şirkət izlənilir.",
            "risk_level": "Orta",
            "recommendation": "Daha çox şirkət əlavə edərək diversifikasiyanı artırın."
        })

@app.route('/api/company-forecast', methods=['POST'])
@token_required
def company_forecast(current_user, role, user_id):
    data = request.json
    company_id = data.get('company_id')
    
    company = next((c for c in COMPANIES_DATA if c['id'] == company_id), None)
    
    if not company:
        return jsonify({"error": "Şirkət tapılmadı"}), 404
    
    prompt = f"""
    Sən maliyyə analitikisən. Aşağıdakı şirkətin 3 illik gələcək proqnozunu ver.
    
    Şirkət: {json.dumps(company, ensure_ascii=False)}
    
    Cavabını JSON formatında ver:
    {{
        "growth_forecast": {{
            "year_1": "%-lə artım",
            "year_2": "%-lə artım",
            "year_3": "%-lə artım"
        }},
        "esg_trajectory": {{
            "current": {company['esg_score']},
            "year_1": "proqnoz",
            "year_2": "proqnoz",
            "year_3": "proqnoz"
        }},
        "market_position": "Bazar mövqeyi analizi",
        "opportunities": ["fürsət 1", "fürsət 2"],
        "threats": ["təhdid 1", "təhdid 2"],
        "investment_recommendation": "Al/Saxla/Sat",
        "confidence_level": "Yüksək/Orta/Aşağı",
        "summary": "Qısa proqnoz"
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        return jsonify({"company": company, "forecast": json.loads(result.strip())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================== Kids APIs ==========================
@app.route('/api/kids-chat', methods=['POST'])
@token_required
def kids_chat(current_user, role, user_id):
    data = request.json
    message = data.get('message', '')
    
    prompt = f"""
    Sən uşaqlar üçün maliyyə məsləhətçisisən. 8-16 yaş arası uşaqlara sadə və əyləncəli şəkildə maliyyə savadlılığı öyrədirsən.
    
    Uşağın sualı: {message}
    
    Qaydalar:
    1. Sadə dildə cavab ver
    2. Emoji istifadə et
    3. Nümunələr ver
    4. Həvəsləndirici ol
    5. Azərbaycan manatı (AZN) ilə nümunələr ver
    6. Maksimum 150 söz
    
    Cavab ver:
    """
    
    try:
        response = model.generate_content(prompt)
        ai_response = response.text.strip()
        
        # Save chat to history
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO chat_history (user_id, role, message, response, chat_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (user_id, role, message, ai_response, 'kids_chat'))
        conn.commit()
        conn.close()
        
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/kids/progress', methods=['GET'])
@token_required
def get_kids_progress(current_user, role, user_id):
    """Get kids progress data"""
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT xp, level, badges_count, lessons_completed, tasks_completed, ethical_score FROM kids_progress WHERE user_id = ?', (user_id,))
    progress = cursor.fetchone()
    
    # Create initial progress if none exists
    if not progress:
        cursor.execute('''
            INSERT INTO kids_progress (user_id, xp, level, badges_count, lessons_completed, tasks_completed, ethical_score)
            VALUES (?, 0, 1, 0, 0, 0, 50)
        ''', (user_id,))
        conn.commit()
        progress = (0, 1, 0, 0, 0, 50)
    
    cursor.execute('SELECT badge_name, badge_icon, earned_at FROM kids_badges WHERE user_id = ? ORDER BY earned_at DESC', (user_id,))
    badges = cursor.fetchall()
    
    cursor.execute('SELECT lesson_id, lesson_name, xp_earned, completed_at FROM kids_lessons WHERE user_id = ? ORDER BY completed_at DESC', (user_id,))
    lessons = cursor.fetchall()
    
    cursor.execute('SELECT task_id, task_name, company_name, badge_earned, xp_earned, completed_at FROM kids_tasks WHERE user_id = ? ORDER BY completed_at DESC', (user_id,))
    tasks = cursor.fetchall()
    
    conn.close()
    
    return jsonify({
        "xp": progress[0],
        "level": progress[1],
        "badges_count": progress[2],
        "lessons_completed": progress[3],
        "tasks_completed": progress[4],
        "ethical_score": progress[5],
        "badges": [{"name": b[0], "icon": b[1], "earned_at": b[2]} for b in badges],
        "lessons": [{"id": l[0], "name": l[1], "xp": l[2], "completed_at": l[3]} for l in lessons],
        "tasks": [{"id": t[0], "name": t[1], "company": t[2], "badge": t[3], "xp": t[4], "completed_at": t[5]} for t in tasks]
    })

@app.route('/api/kids/complete-lesson', methods=['POST'])
@token_required
def complete_lesson(current_user, role, user_id):
    """Mark a lesson as completed"""
    data = request.json
    lesson_id = data.get('lesson_id')
    lesson_name = data.get('lesson_name')
    xp_reward = data.get('xp', 30)
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Check if already completed
    cursor.execute('SELECT id FROM kids_lessons WHERE user_id = ? AND lesson_id = ?', (user_id, lesson_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "Lesson already completed", "already_completed": True})
    
    # Add lesson completion
    cursor.execute('''
        INSERT INTO kids_lessons (user_id, lesson_id, lesson_name, xp_earned)
        VALUES (?, ?, ?, ?)
    ''', (user_id, lesson_id, lesson_name, xp_reward))
    
    # Update progress
    cursor.execute('''
        UPDATE kids_progress 
        SET xp = xp + ?, lessons_completed = lessons_completed + 1, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (xp_reward, user_id))
    
    # Check for level up
    cursor.execute('SELECT xp, level FROM kids_progress WHERE user_id = ?', (user_id,))
    progress = cursor.fetchone()
    new_level = (progress[0] // 100) + 1
    if new_level > progress[1]:
        cursor.execute('UPDATE kids_progress SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "xp_earned": xp_reward,
        "message": f"🎉 Təbrik! {lesson_name} dərsini bitirdin! +{xp_reward} XP"
    })

@app.route('/api/kids/complete-task', methods=['POST'])
@token_required
def complete_kids_task(current_user, role, user_id):
    """Mark a task as completed and award badge"""
    data = request.json
    task_id = data.get('task_id')
    task_name = data.get('task_name')
    company_name = data.get('company_name')
    badge_name = data.get('badge_name')
    xp_reward = data.get('xp', 35)
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    # Check if already completed
    cursor.execute('SELECT id FROM kids_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id))
    if cursor.fetchone():
        conn.close()
        return jsonify({"message": "Task already completed", "already_completed": True})
    
    # Add task completion
    cursor.execute('''
        INSERT INTO kids_tasks (user_id, task_id, task_name, company_name, badge_earned, xp_earned)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, task_id, task_name, company_name, badge_name, xp_reward))
    
    # Add badge
    cursor.execute('''
        INSERT INTO kids_badges (user_id, badge_name, badge_icon)
        VALUES (?, ?, ?)
    ''', (user_id, badge_name, '🏆'))
    
    # Update progress
    cursor.execute('''
        UPDATE kids_progress 
        SET xp = xp + ?, tasks_completed = tasks_completed + 1, badges_count = badges_count + 1, 
            ethical_score = MIN(100, ethical_score + 5), updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (xp_reward, user_id))
    
    # Check for level up
    cursor.execute('SELECT xp, level FROM kids_progress WHERE user_id = ?', (user_id,))
    progress = cursor.fetchone()
    new_level = (progress[0] // 100) + 1
    if new_level > progress[1]:
        cursor.execute('UPDATE kids_progress SET level = ? WHERE user_id = ?', (new_level, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "xp_earned": xp_reward,
        "badge_earned": badge_name,
        "message": f"🎉 Möhtəşəm! {badge_name} qazandın! +{xp_reward} XP"
    })

@app.route('/api/kids/simulator-action', methods=['POST'])
@token_required
def simulator_action(current_user, role, user_id):
    """Handle business simulator actions"""
    data = request.json
    action = data.get('action')
    
    changes = {
        'eco': {'balance': -5, 'ethical': 15, 'sold': 0},
        'cheap': {'balance': 10, 'ethical': -10, 'sold': 2},
        'donate': {'balance': -10, 'ethical': 20, 'sold': 0},
        'marketing': {'balance': -8, 'ethical': 0, 'sold': 5}
    }
    
    if action not in changes:
        return jsonify({"error": "Invalid action"}), 400
    
    change = changes[action]
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE business_simulator 
        SET balance = MAX(0, balance + ?), 
            ethical_score = MAX(0, MIN(100, ethical_score + ?)),
            items_sold = items_sold + ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    ''', (change['balance'], change['ethical'], change['sold'], user_id))
    
    cursor.execute('SELECT balance, items_sold, ethical_score, day FROM business_simulator WHERE user_id = ?', (user_id,))
    state = cursor.fetchone()
    
    conn.commit()
    conn.close()
    
    messages = {
        'eco': '🌱 Əla seçim! Ekoloji düşünmək çox vacibdir.',
        'cheap': '💲 Diqqət! Ucuz material müştəriləri narazı edə bilər.',
        'donate': '❤️ Möhtəşəm! Xeyriyyə etmək cəmiyyətə kömək edir.',
        'marketing': '📢 Yaxşı fikir! Reklam satışları artıracaq.'
    }
    
    return jsonify({
        "success": True,
        "message": messages[action],
        "balance": state[0],
        "items_sold": state[1],
        "ethical_score": state[2],
        "day": state[3]
    })

@app.route('/api/chat-history', methods=['GET'])
@token_required
def get_chat_history(current_user, role, user_id):
    """Get user's chat history"""
    chat_type = request.args.get('type', 'all')
    limit = request.args.get('limit', 50)
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    
    if chat_type == 'all':
        cursor.execute('''
            SELECT message, response, chat_type, created_at 
            FROM chat_history 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
    else:
        cursor.execute('''
            SELECT message, response, chat_type, created_at 
            FROM chat_history 
            WHERE user_id = ? AND chat_type = ?
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, chat_type, limit))
    
    history = cursor.fetchall()
    conn.close()
    
    return jsonify({
        "history": [
            {"message": h[0], "response": h[1], "type": h[2], "created_at": h[3]}
            for h in history
        ]
    })

@app.route('/api/kids-expense', methods=['POST'])
@token_required
def kids_expense(current_user, role, user_id):
    data = request.json
    expenses = data.get('expenses', [])
    allowance = data.get('allowance', 0)
    goal = data.get('goal', '')
    goal_amount = data.get('goal_amount', 0)
    
    total_expenses = sum(e.get('amount', 0) for e in expenses)
    remaining = allowance - total_expenses
    
    prompt = f"""
    Sən uşaqlar üçün maliyyə məsləhətçisisən. Aşağıdakı məlumatlara əsasən uşağa sadə və əyləncəli maliyyə məsləhəti ver.
    
    Aylıq cib xərclıiyi: {allowance} AZN
    Xərclər: {json.dumps(expenses, ensure_ascii=False)}
    Cəmi xərclənib: {total_expenses} AZN
    Qalan: {remaining} AZN
    Hədəf: {goal}
    Hədəf məbləği: {goal_amount} AZN
    
    Cavabını JSON formatında ver:
    {{
        "summary": "Ümumi vəziyyət (emoji ilə)",
        "savings_tip": "Qənaət məsləhəti",
        "fun_fact": "Maraqlı maliyyə faktı",
        "goal_progress": "Hədəfə nə qədər qalıb",
        "achievement": "Əldə etdiyi uğur (həvəsləndirici)",
        "next_step": "Növbəti addım tövsiyəsi"
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        analysis = json.loads(result.strip())
        return jsonify({
            "total_expenses": total_expenses,
            "remaining": remaining,
            "analysis": analysis
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/kids-save-expense', methods=['POST'])
@token_required
def kids_save_expense(current_user, role, user_id):
    data = request.json
    category = data.get('category', '')
    amount = data.get('amount', 0)
    
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO kids_expenses (user_id, category, amount) VALUES (?, ?, ?)',
            (user_id, category, amount)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "Xərc əlavə edildi!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================== Future Talent Bridge APIs ==========================
@app.route('/api/tasks', methods=['GET'])
@token_required
def get_tasks(current_user, role, user_id):
    """Get available tasks from companies for kids"""
    # Demo tasks from companies
    tasks = [
        {
            "id": 1,
            "company": "AzərEnerji Plus",
            "title": "Loqo Seçimi",
            "description": "3 loqo arasından ən uyğununu seç",
            "duration": "3 dəq",
            "badge": "Dizayner Badge",
            "xp": 25,
            "category": "Kreativ"
        },
        {
            "id": 2,
            "company": "GreenBuild Azerbaijan",
            "title": "Büdcə Bölgüsü",
            "description": "100 AZN-i 3 kateqoriyaya böl",
            "duration": "5 dəq",
            "badge": "Maliyyəçi Badge",
            "xp": 35,
            "category": "Maliyyə"
        },
        {
            "id": 3,
            "company": "EcoTextile Group",
            "title": "Marketinq İdeyası",
            "description": "Yaşıl məhsul üçün reklam ideyası ver",
            "duration": "10 dəq",
            "badge": "Kreativ Badge",
            "xp": 50,
            "category": "Marketinq"
        },
        {
            "id": 4,
            "company": "AgriTech Baku",
            "title": "ESG Quizi",
            "description": "Ətraf mühit haqqında 5 suallıq quiz həll et",
            "duration": "5 dəq",
            "badge": "Ekoloji Badge",
            "xp": 30,
            "category": "Təhsil"
        }
    ]
    return jsonify({"tasks": tasks})

@app.route('/api/tasks/complete', methods=['POST'])
@token_required
def complete_task(current_user, role, user_id):
    """Mark a task as completed"""
    data = request.json
    task_id = data.get('task_id')
    answer = data.get('answer', '')
    
    # Simulate task completion and badge awarding
    badges = {
        1: {"name": "Dizayner", "xp": 25},
        2: {"name": "Maliyyəçi", "xp": 35},
        3: {"name": "Kreativ", "xp": 50},
        4: {"name": "Ekoloji", "xp": 30}
    }
    
    badge_info = badges.get(task_id, {"name": "Uğur", "xp": 20})
    
    return jsonify({
        "success": True,
        "badge_earned": badge_info["name"],
        "xp_earned": badge_info["xp"],
        "message": f"Təbrik edirik! {badge_info['name']} Badge qazandın! 🎉"
    })

@app.route('/api/company/post-task', methods=['POST'])
@token_required
def post_task(current_user, role, user_id):
    """Companies can post tasks for kids"""
    if role != 'enterprise':
        return jsonify({"error": "Only companies can post tasks"}), 403
    
    data = request.json
    
    prompt = f"""
    Sən uşaqlar üçün tapşırıq dizayneriysən. Şirkət aşağıdakı tapşırığı paylaşmaq istəyir.
    
    Tapşırıq məlumatları:
    - Başlıq: {data.get('title', '')}
    - Təsvir: {data.get('description', '')}
    - Kateqoriya: {data.get('category', '')}
    
    Bu tapşırığı 8-16 yaş uşaqlar üçün uyğunlaşdır və aşağıdakı formatda qaytar:
    
    {{
        "title": "Uşaq dostu başlıq",
        "description": "Sadə və aydın təsvir",
        "duration": "təxmini müddət",
        "badge_name": "Badge adı",
        "xp_reward": 20-50 arası rəqəm,
        "learning_outcome": "Bu tapşırıqdan öyrəniləcək şey"
    }}
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        
        task_data = json.loads(result.strip())
        task_data["company"] = current_user.capitalize()
        task_data["company_id"] = user_id
        
        # Save task to database
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO talent_tasks (company_id, company_name, title, description, duration, badge_name, xp_reward, learning_outcome)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id,
            current_user.capitalize(),
            task_data.get('title', data.get('title', '')),
            task_data.get('description', data.get('description', '')),
            task_data.get('duration', '5 dəqiqə'),
            task_data.get('badge_name', data.get('badge', 'Tapşırıq Badge')),
            task_data.get('xp_reward', 30),
            task_data.get('learning_outcome', '')
        ))
        task_data['id'] = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "task": task_data})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/talent-tasks', methods=['GET'])
def get_talent_tasks():
    """Get all tasks posted by companies for kids"""
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, company_name, title, description, duration, badge_name, xp_reward, completions
            FROM talent_tasks
            ORDER BY created_at DESC
        ''')
        tasks = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "tasks": [
                {
                    "id": t[0],
                    "company": t[1],
                    "name": t[2],
                    "description": t[3],
                    "duration": t[4],
                    "badge": t[5],
                    "xp": t[6],
                    "completions": t[7]
                }
                for t in tasks
            ]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/investor/portfolio', methods=['GET'])
@token_required
def get_portfolio(current_user, role, user_id):
    """Get investor's portfolio data"""
    if role != 'investor':
        return jsonify({"error": "Access denied"}), 403
    
    # Demo portfolio data
    portfolio = {
        "total_invested": 250000,
        "total_value": 287500,
        "roi_percent": 15.0,
        "holdings": [
            {"company_id": 1, "name": "AzərEnerji Plus", "invested": 100000, "current_value": 115200, "esg_score": 72, "change": 15.2},
            {"company_id": 3, "name": "AgriTech Baku", "invested": 80000, "current_value": 94800, "esg_score": 78, "change": 18.5},
            {"company_id": 5, "name": "CleanWater Solutions", "invested": 70000, "current_value": 77500, "esg_score": 85, "change": 10.7}
        ],
        "esg_impact": {
            "average_esg": 78.3,
            "carbon_reduced": "45 ton CO2",
            "social_impact": "120 iş yeri yaradılıb"
        }
    }
    return jsonify(portfolio)

@app.route('/api/investor/add-to-portfolio', methods=['POST'])
@token_required
def add_to_portfolio(current_user, role, user_id):
    """Add company to investor's watchlist/portfolio"""
    if role != 'investor':
        return jsonify({"error": "Access denied"}), 403
    
    data = request.json
    company_id = data.get('company_id')
    amount = data.get('amount', 0)
    
    return jsonify({
        "success": True,
        "message": f"Şirkət portfelə əlavə edildi! İnvestisiya: {amount} AZN"
    })

@app.route('/api/investor/insights', methods=['GET'])
@token_required
def get_investment_insights(current_user, role, user_id):
    """Get AI-powered investment insights"""
    if role != 'investor':
        return jsonify({"error": "Access denied"}), 403
    
    prompt = """
    Sən ESG investisiya məsləhətçisisən. Azərbaycan bazarı üçün 3 investisiya insight ver.
    
    JSON formatında cavab ver:
    {
        "market_outlook": "Bazar gözləntiləri",
        "top_sectors": ["sektor 1", "sektor 2"],
        "insights": [
            {"title": "Insight başlığı", "description": "Qısa açıqlama", "impact": "Yüksək/Orta/Aşağı"}
        ],
        "recommendation": "Ümumi tövsiyə"
    }
    
    Yalnız JSON cavab ver.
    """
    
    try:
        response = model.generate_content(prompt)
        result = response.text.strip()
        if result.startswith('```json'):
            result = result[7:]
        if result.startswith('```'):
            result = result[3:]
        if result.endswith('```'):
            result = result[:-3]
        return jsonify(json.loads(result.strip()))
    except Exception as e:
        return jsonify({
            "market_outlook": "Bazar stabil inkişaf edir",
            "top_sectors": ["Yaşıl enerji", "AgriTech"],
            "insights": [
                {"title": "ESG liderliyinin artması", "description": "ESG skorlu şirkətlər daha yüksək investisiya cəlb edir", "impact": "Yüksək"}
            ],
            "recommendation": "Yaşıl enerji və texnologiya sektorlarına fokuslanın"
        })

@app.route('/api/future-talent/stats', methods=['GET'])
@token_required
def future_talent_stats(current_user, role, user_id):
    """Get Future Talent ecosystem statistics for investors - REAL DATA from database"""
    try:
        # Get total kids enrolled
        user_conn = sqlite3.connect('users.db')
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'kids'")
        total_kids = user_cursor.fetchone()[0]
        user_conn.close()
        
        # Get stats from data.db
        data_conn = sqlite3.connect('data.db')
        data_cursor = data_conn.cursor()
        
        # Total badges
        data_cursor.execute("SELECT COUNT(*) FROM kids_badges")
        badges_awarded = data_cursor.fetchone()[0]
        
        # Total tasks completed
        data_cursor.execute("SELECT COUNT(*) FROM kids_tasks")
        tasks_completed = data_cursor.fetchone()[0]
        
        # Total lessons completed
        data_cursor.execute("SELECT COUNT(*) FROM kids_lessons")
        lessons_completed = data_cursor.fetchone()[0]
        
        # Average ethical score (financial literacy proxy)
        data_cursor.execute("SELECT AVG(ethical_score), AVG(xp) FROM kids_progress")
        progress_result = data_cursor.fetchone()
        avg_ethical = progress_result[0] if progress_result[0] else 50
        avg_xp = progress_result[1] if progress_result[1] else 0
        
        data_conn.close()
        
        return jsonify({
            "total_kids_enrolled": total_kids or 0,
            "badges_awarded": badges_awarded or 0,
            "tasks_completed": tasks_completed or 0,
            "lessons_completed": lessons_completed or 0,
            "average_financial_literacy": round(avg_ethical) if avg_ethical else 0,
            "esg_awareness_score": min(round(avg_ethical * 1.1), 100) if avg_ethical else 0,
            "monthly_growth": 0,  # Would need historical data
            "top_skills": ["Büdcələmə", "Qənaət", "ESG Anlayışı"],
            "active_companies": 0
        })
    except Exception as e:
        print(f"Error getting future talent stats: {e}")
        return jsonify({
            "total_kids_enrolled": 0,
            "badges_awarded": 0,
            "tasks_completed": 0,
            "lessons_completed": 0,
            "average_financial_literacy": 0,
            "esg_awareness_score": 0,
            "monthly_growth": 0,
            "top_skills": [],
            "active_companies": 0
        })

# ========================== Multiple Account Management ==========================
@app.route('/api/accounts', methods=['GET'])
@token_required
def get_accounts(current_user, role, user_id):
    """Get all accounts associated with a user (in this implementation, just the current account)"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, category, created_at FROM users WHERE username = ?", (current_user,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                "accounts": [{
                    "id": result[0],
                    "username": result[1],
                    "role": result[2],
                    "category": result[3],
                    "created_at": result[4],
                    "is_active": True
                }]
            })
        return jsonify({"accounts": []})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/switch-account', methods=['POST'])
def switch_account():
    """Switch to a different account"""
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '')
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, password, role FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            user_id, stored_hash, role = result
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                token_duration = datetime.timedelta(days=15)
                
                payload = {
                    'sub': username,
                    'role': role,
                    'id': user_id,
                    'iat': datetime.datetime.now(datetime.UTC),
                    'exp': datetime.datetime.now(datetime.UTC) + token_duration
                }
                
                token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
                
                response = make_response(jsonify({
                    "message": "Hesab dəyişdirildi!",
                    "role": role
                }))
                
                response.set_cookie(
                    'token',
                    token,
                    httponly=True,
                    secure=False,
                    path='/',
                    max_age=int(token_duration.total_seconds())
                )
                
                return response, 200
        
        return jsonify({"message": "Yanlış məlumatlar"}), 401
    except Exception as e:
        return jsonify({"message": f"Xəta: {str(e)}"}), 500

@app.route('/api/user/profile', methods=['GET'])
@token_required
def get_user_profile(current_user, role, user_id):
    """Get current user's profile"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, category, created_at FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                "id": result[0],
                "username": result[1],
                "role": result[2],
                "category": result[3],
                "created_at": result[4]
            })
        return jsonify({"error": "User not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/accounts/all', methods=['GET'])
@token_required
def get_all_accounts(current_user, role, user_id):
    """Get all accounts in the system (for account switching)"""
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, category, created_at FROM users ORDER BY created_at DESC")
        accounts = cursor.fetchall()
        conn.close()
        
        return jsonify({
            "accounts": [
                {
                    "id": a[0],
                    "username": a[1],
                    "role": a[2],
                    "category": a[3],
                    "created_at": a[4],
                    "is_current": a[0] == user_id
                }
                for a in accounts
            ],
            "current_user_id": user_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/accounts/switch/<int:target_user_id>', methods=['POST'])
@token_required
def switch_to_account(current_user, role, user_id, target_user_id):
    """Switch to another account (requires password)"""
    data = request.json
    password = data.get('password', '')
    
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, password, role FROM users WHERE id = ?", (target_user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            target_id, target_username, stored_hash, target_role = result
            if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                token_duration = datetime.timedelta(days=15)
                
                payload = {
                    'sub': target_username,
                    'role': target_role,
                    'id': target_id,
                    'iat': datetime.datetime.now(datetime.UTC),
                    'exp': datetime.datetime.now(datetime.UTC) + token_duration
                }
                
                token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
                
                response = make_response(jsonify({
                    "success": True,
                    "message": f"Hesab dəyişdirildi: {target_username}",
                    "role": target_role
                }))
                
                response.set_cookie(
                    'token',
                    token,
                    httponly=True,
                    secure=False,
                    path='/',
                    max_age=int(token_duration.total_seconds())
                )
                
                return response, 200
            else:
                return jsonify({"error": "Yanlış şifrə"}), 401
        
        return jsonify({"error": "Hesab tapılmadı"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/accounts/delete/<int:target_user_id>', methods=['DELETE'])
@token_required
def delete_account(current_user, role, user_id, target_user_id):
    """Delete an account"""
    if target_user_id == user_id:
        return jsonify({"error": "Cari hesabı silə bilməzsiniz"}), 400
    
    try:
        # Delete from users.db
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = ?", (target_user_id,))
        conn.commit()
        conn.close()
        
        # Delete related data from data.db
        data_conn = sqlite3.connect('data.db')
        data_cursor = data_conn.cursor()
        data_cursor.execute("DELETE FROM predictions WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM company_data WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_expenses WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_goals WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_progress WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_badges WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_lessons WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM kids_tasks WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM chat_history WHERE user_id = ?", (target_user_id,))
        data_cursor.execute("DELETE FROM business_simulator WHERE user_id = ?", (target_user_id,))
        data_conn.commit()
        data_conn.close()
        
        return jsonify({"success": True, "message": "Hesab silindi"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ========================== Stats APIs ==========================
@app.route('/api/stats/companies', methods=['GET'])
@token_required
def get_company_stats(current_user, role, user_id):
    # Get real stats from database
    try:
        user_conn = sqlite3.connect('users.db')
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'enterprise'")
        total_companies = user_cursor.fetchone()[0]
        user_conn.close()
        
        data_conn = sqlite3.connect('data.db')
        data_cursor = data_conn.cursor()
        data_cursor.execute("SELECT AVG(esg_score), COUNT(*) FROM company_data WHERE esg_score >= 70")
        result = data_cursor.fetchone()
        
        data_cursor.execute("SELECT AVG(esg_score) FROM company_data WHERE esg_score IS NOT NULL")
        avg_esg_result = data_cursor.fetchone()
        data_conn.close()
        
        return jsonify({
            "total_companies": max(total_companies, len(COMPANIES_DATA)),
            "average_esg": avg_esg_result[0] if avg_esg_result[0] else sum(c['esg_score'] for c in COMPANIES_DATA) / len(COMPANIES_DATA),
            "compliant_count": result[1] if result[1] else len([c for c in COMPANIES_DATA if c['esg_score'] >= 70])
        })
    except:
        return jsonify({
            "total_companies": len(COMPANIES_DATA),
            "average_esg": sum(c['esg_score'] for c in COMPANIES_DATA) / len(COMPANIES_DATA),
            "compliant_count": len([c for c in COMPANIES_DATA if c['esg_score'] >= 70])
        })

@app.route('/api/my-company-data', methods=['GET'])
@token_required
def get_my_company_data(current_user, role, user_id):
    """Get current company's ESG data from database"""
    if role != 'enterprise':
        return jsonify({"error": "Only companies can access this"}), 403
    
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        # Get latest company ESG data
        cursor.execute("""
            SELECT esg_score, environmental_score, social_score, governance_score, eu_compliance, notes, created_at 
            FROM company_data 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        company_data = cursor.fetchone()
        
        # Get latest predictions
        cursor.execute("""
            SELECT int_rate, default_rate, sus_score 
            FROM predictions 
            WHERE user_id = ? 
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,))
        predictions = cursor.fetchone()
        
        conn.close()
        
        # Get user category from users.db
        user_conn = sqlite3.connect('users.db')
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT category FROM users WHERE id = ?", (user_id,))
        category_result = user_cursor.fetchone()
        user_conn.close()
        
        if company_data:
            return jsonify({
                "has_data": True,
                "esg_score": company_data[0] or 0,
                "environmental_score": company_data[1] or 0,
                "social_score": company_data[2] or 0,
                "governance_score": company_data[3] or 0,
                "eu_compliance": company_data[4] or "Yoxlanılmayıb",
                "category": category_result[0] if category_result else "Ümumi",
                "int_rate": predictions[0] if predictions else None,
                "default_rate": predictions[1] if predictions else None,
                "sus_score": predictions[2] if predictions else None
            })
        else:
            return jsonify({
                "has_data": False,
                "esg_score": 0,
                "environmental_score": 0,
                "social_score": 0,
                "governance_score": 0,
                "eu_compliance": "Yoxlanılmayıb",
                "category": category_result[0] if category_result else "Ümumi",
                "message": "ESG qiymətləndirməsi tamamlanmayıb. Assessment bölməsindən başlayın."
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/save-esg-data', methods=['POST'])
@token_required
def save_esg_data(current_user, role, user_id):
    """Save company ESG assessment data"""
    if role != 'enterprise':
        return jsonify({"error": "Only companies can save ESG data"}), 403
    
    data = request.json
    
    try:
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO company_data (user_id, esg_score, environmental_score, social_score, governance_score, eu_compliance, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id,
            data.get('esg_score', 0),
            data.get('environmental_score', 0),
            data.get('social_score', 0),
            data.get('governance_score', 0),
            data.get('eu_compliance', ''),
            data.get('notes', '')
        ))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "ESG məlumatları saxlanıldı"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/future-talent', methods=['GET'])
@token_required
def get_future_talent_stats(current_user, role, user_id):
    """Get stats about kids/youth engagement for investors"""
    try:
        # Get total kids enrolled
        user_conn = sqlite3.connect('users.db')
        user_cursor = user_conn.cursor()
        user_cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'kids'")
        total_kids = user_cursor.fetchone()[0]
        user_conn.close()
        
        # Get stats from data.db
        data_conn = sqlite3.connect('data.db')
        data_cursor = data_conn.cursor()
        
        # Total badges
        data_cursor.execute("SELECT COUNT(*) FROM kids_badges")
        badges_awarded = data_cursor.fetchone()[0]
        
        # Total tasks completed
        data_cursor.execute("SELECT COUNT(*) FROM kids_tasks")
        tasks_completed = data_cursor.fetchone()[0]
        
        # Average ethical score (financial literacy proxy)
        data_cursor.execute("SELECT AVG(ethical_score), AVG(xp) FROM kids_progress")
        progress_result = data_cursor.fetchone()
        avg_ethical = progress_result[0] if progress_result[0] else 50
        avg_xp = progress_result[1] if progress_result[1] else 0
        
        # Lessons completed
        data_cursor.execute("SELECT COUNT(*) FROM kids_lessons")
        lessons_completed = data_cursor.fetchone()[0]
        
        data_conn.close()
        
        return jsonify({
            "total_kids_enrolled": total_kids or 0,
            "badges_awarded": badges_awarded or 0,
            "tasks_completed": tasks_completed or 0,
            "lessons_completed": lessons_completed or 0,
            "average_financial_literacy": round(avg_ethical),
            "esg_awareness_score": min(round(avg_ethical * 1.1), 100),  # Estimated ESG awareness
            "monthly_growth": 15.3,  # This would need historical data to calculate
            "total_xp_earned": round(avg_xp * total_kids) if total_kids else 0
        })
    except Exception as e:
        print(f"Error getting future talent stats: {e}")
        return jsonify({
            "total_kids_enrolled": 0,
            "badges_awarded": 0,
            "tasks_completed": 0,
            "lessons_completed": 0,
            "average_financial_literacy": 50,
            "esg_awareness_score": 55,
            "monthly_growth": 0,
            "total_xp_earned": 0
        })

@app.route('/get-esg-tip', methods=['POST'])
def get_esg_tip():
    """Get ESG tip from AI"""
    prompt = "Generate a short, actionable ESG tip for a company dashboard. Single sentence, innovative and inspiring."
    
    try:
        response = model.generate_content(prompt)
        return jsonify({'tip': response.text.strip()})
    except:
        return jsonify({'tip': 'Focus on reducing energy consumption to improve ESG scores.'}), 200

@app.route('/get_gemini_news')
def get_gemini_news():
    """Get ESG news from Gemini"""
    sys_prompt = '''
    Find a recent news article about EU ESG/CSRD rules affecting SMEs.
    Return in format: [headline]*[summary under 25 words]*[URL]
    '''
    
    prompt = news_prompts[random.randrange(0, len(news_prompts))]
    
    try:
        response = model.generate_content(sys_prompt + "\n" + prompt)
        output = response.text.strip()
        
        parts = output.split('*')
        parts = [p.strip() for p in parts if p.strip()]
        
        if len(parts) >= 3:
            return jsonify({
                'title': parts[0],
                'summary': parts[1],
                'link': parts[2] if parts[2].startswith('http') else f'https://{parts[2]}'
            }), 200
        else:
            return jsonify({
                'title': 'EU ESG Updates',
                'summary': 'New regulations affecting SMEs across Europe.',
                'link': 'https://ec.europa.eu/info/business-economy-euro/banking-and-finance/sustainable-finance_en'
            }), 200
    except:
        return jsonify({
            'title': 'EU ESG News',
            'summary': 'Latest sustainability reporting requirements for businesses.',
            'link': 'https://ec.europa.eu/info/business-economy-euro/banking-and-finance/sustainable-finance_en'
        }), 200

@app.route('/get_data', methods=['GET'])
@token_required
def get_data_csv(current_user, role, user_id):
    """Export predictions as CSV"""
    import pandas as pd
    
    conn = sqlite3.connect('data.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT int_rate, default_rate, sus_score FROM predictions WHERE user_id=?',
        (user_id,)
    )
    data = cursor.fetchall()
    conn.close()
    
    df = pd.DataFrame(data, columns=['interest_rate', 'default_rate', 'sus_score'])
    csv_string = df.to_csv(index=False)
    
    response = make_response(csv_string)
    response.headers["Content-Disposition"] = "attachment; filename=predictions_export.csv"
    response.headers["Content-type"] = "text/csv"
    
    return response

# ========================== Run Server ==========================
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
