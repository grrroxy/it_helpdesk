from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, flash
import sqlite3
import os
import random
import string
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'ultra_secret_key_2026_magnat'
app.config['UPLOAD_FOLDER'] = 'static/avatars'
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB

# ===== ДЛЯ RENDER.COM =====
DB_PATH = '/tmp/database.db'
# ==========================

# Создаем папку для аватарок если её нет
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# 6 аватарок для сотрудников (без наушников)
EMPLOYEE_AVATARS = ['emp_avatar1.png', 'emp_avatar2.png', 'emp_avatar3.png', 'emp_avatar4.png', 'emp_avatar5.png', 'emp_avatar6.png']

# 6 аватарок для IT-специалистов (с наушниками и микрофонами)
IT_AVATARS = ['it_avatar1.png', 'it_avatar2.png', 'it_avatar3.png', 'it_avatar4.png', 'it_avatar5.png', 'it_avatar6.png']

# Все стандартные аватарки
DEFAULT_AVATARS = EMPLOYEE_AVATARS + IT_AVATARS

def init_db():
    # Исправляем предупреждение о datetime
    sqlite3.register_adapter(datetime, lambda dt: dt.isoformat())
    sqlite3.register_converter("timestamp", lambda v: datetime.fromisoformat(v.decode()))
    
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            full_name TEXT NOT NULL,
            avatar TEXT DEFAULT 'emp_avatar1.png',
            is_verified INTEGER DEFAULT 1,
            verification_code TEXT,
            verification_code_expires TIMESTAMP,
            reset_code TEXT,
            reset_code_expires TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT,
            category TEXT DEFAULT 'Техническая',
            priority TEXT DEFAULT 'Средний',
            status TEXT DEFAULT 'open',
            created_by TEXT NOT NULL,
            created_by_id INTEGER,
            created_by_name TEXT,
            created_by_avatar TEXT,
            accepted_by TEXT DEFAULT NULL,
            accepted_by_id INTEGER DEFAULT NULL,
            accepted_by_name TEXT DEFAULT NULL,
            accepted_by_avatar TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            resolved_at TIMESTAMP DEFAULT NULL
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT,
            action TEXT,
            ticket_id INTEGER,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("=" * 60)
    print("✅ База данных готова!")
    print("👥 НЕТ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ!")
    print("📝 Первый пользователь должен зарегистрироваться")
    print("=" * 60)

def generate_code():
    return ''.join(random.choices(string.digits, k=6))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        role = request.form.get('role', 'employee')
        
        if not full_name:
            return render_template('register.html', error='Введите ФИО')
        if not email:
            return render_template('register.html', error='Введите Email')
        if len(password) < 6:
            return render_template('register.html', error='Пароль должен содержать минимум 6 символов')
        
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        cur.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email))
        existing = cur.fetchone()
        
        if existing:
            conn.close()
            return render_template('register.html', error='Такой логин или Email уже существует')
        
        # Выбираем дефолтную аватарку в зависимости от роли
        default_avatar = 'emp_avatar1.png' if role == 'employee' else 'it_avatar1.png'
        
        # РЕГИСТРАЦИЯ БЕЗ ПОДТВЕРЖДЕНИЯ ПОЧТЫ
        cur.execute('''
            INSERT INTO users (username, email, password, role, full_name, avatar, is_verified)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        ''', (username, email, password, role, full_name, default_avatar))
        
        user_id = cur.lastrowid
        conn.commit()
        conn.close()
        
        flash('✅ Регистрация успешна! Теперь войдите в систему.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/verify_email', methods=['GET', 'POST'])
def verify_email():
    # Перенаправляем на логин, так как подтверждение не требуется
    return redirect(url_for('login'))

@app.route('/resend_code', methods=['POST'])
def resend_code():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    saved_username = request.cookies.get('saved_username')
    saved_password = request.cookies.get('saved_password')
    
    if saved_username and saved_password and request.method == 'GET':
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (saved_username, saved_password))
        user = cur.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['avatar'] = user['avatar']
            return redirect(url_for('tickets_page'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember') == 'on'
        
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
        user = cur.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            session['avatar'] = user['avatar']
            
            response = make_response(redirect(url_for('tickets_page')))
            
            if remember:
                response.set_cookie('saved_username', username, max_age=30*24*60*60, httponly=True)
                response.set_cookie('saved_password', password, max_age=30*24*60*60, httponly=True)
            else:
                response.set_cookie('saved_username', '', expires=0)
                response.set_cookie('saved_password', '', expires=0)
            
            return response
        else:
            return render_template('login.html', error='Неверный логин или пароль')
    
    return render_template('login.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    # Просто заглушка для восстановления пароля
    return render_template('forgot_password.html', error='Функция восстановления пароля временно недоступна')

@app.route('/verify_reset_code', methods=['GET', 'POST'])
def verify_reset_code():
    return redirect(url_for('login'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    return redirect(url_for('login'))

# ===== ЗАГРУЗКА АВАТАРКИ =====
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if 'avatar_file' in request.files:
        file = request.files['avatar_file']
        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            filename = f"user_{session['user_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("UPDATE users SET avatar = ? WHERE id = ?", (filename, session['user_id']))
            conn.commit()
            conn.close()
            
            session['avatar'] = filename
            return redirect(url_for('profile'))
    
    return redirect(url_for('profile'))

@app.route('/set_avatar/<avatar_name>')
def set_avatar(avatar_name):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if avatar_name in DEFAULT_AVATARS or avatar_name.startswith('user_'):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar_name, session['user_id']))
        conn.commit()
        conn.close()
        session['avatar'] = avatar_name
    
    return redirect(url_for('profile'))

# ===== УПРАВЛЕНИЕ ПРОФИЛЕМ =====

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],))
    user = cur.fetchone()
    conn.close()
    
    if user is None:
        session.clear()
        return redirect(url_for('login'))
    
    available_avatars = []
    if user['role'] == 'employee':
        for f in EMPLOYEE_AVATARS:
            if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f)):
                available_avatars.append(f)
    else:
        for f in IT_AVATARS:
            if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], f)):
                available_avatars.append(f)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            new_full_name = request.form.get('full_name', '').strip()
            new_username = request.form.get('username', '').strip()
            
            if not new_full_name:
                return render_template('profile.html', user=user, available_avatars=available_avatars, error='ФИО не может быть пустым')
            if not new_username:
                return render_template('profile.html', user=user, available_avatars=available_avatars, error='Логин не может быть пустым')
            
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            try:
                cur.execute("UPDATE users SET full_name = ?, username = ? WHERE id = ?",
                           (new_full_name, new_username, session['user_id']))
                conn.commit()
                session['full_name'] = new_full_name
                session['username'] = new_username
                conn.close()
                return render_template('profile.html', user=user, available_avatars=available_avatars, success='Данные обновлены!')
            except sqlite3.IntegrityError:
                conn.close()
                return render_template('profile.html', user=user, available_avatars=available_avatars, error='Такой логин уже существует')
        
        elif action == 'request_password_change':
            # Временно отключено
            return render_template('profile.html', user=user, available_avatars=available_avatars, error='Функция смены пароля временно недоступна')
        
        elif action == 'change_password':
            return render_template('profile.html', user=user, available_avatars=available_avatars, error='Функция смены пароля временно недоступна')
    
    return render_template('profile.html', user=user, available_avatars=available_avatars)

@app.route('/logout')
def logout():
    session.clear()
    response = make_response(redirect(url_for('login')))
    response.set_cookie('saved_username', '', expires=0)
    response.set_cookie('saved_password', '', expires=0)
    return response

@app.route('/')
def root():
    return redirect(url_for('tickets_page'))

@app.route('/tickets')
def tickets_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    if session['role'] == 'employee':
        cur.execute("SELECT * FROM tickets WHERE created_by = ? ORDER BY id DESC", (session['username'],))
    else:
        cur.execute("SELECT * FROM tickets ORDER BY id DESC")
    
    tickets = cur.fetchall()
    conn.close()
    
    return render_template('tickets.html', tickets=tickets, role=session['role'], full_name=session['full_name'], username=session['username'], avatar=session.get('avatar', 'emp_avatar1.png'))

@app.route('/add_ticket', methods=['POST'])
def add_ticket():
    if 'user_id' not in session or session['role'] not in ['employee', 'admin']:
        return redirect(url_for('tickets_page'))
    
    title = request.form['title']
    description = request.form['description']
    location = request.form.get('location', '')
    category = request.form.get('category', 'Техническая')
    priority = request.form.get('priority', 'Средний')
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO tickets (title, description, location, category, priority, created_by, created_by_id, created_by_name, created_by_avatar, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')
    ''', (title, description, location, category, priority, session['username'], session['user_id'], session['full_name'], session.get('avatar', 'emp_avatar1.png')))
    
    ticket_id = cur.lastrowid
    conn.commit()
    conn.close()
    
    return redirect(url_for('tickets_page'))

@app.route('/take/<int:ticket_id>')
def take_ticket(ticket_id):
    if 'user_id' not in session or session['role'] not in ['it_specialist', 'admin']:
        return redirect(url_for('tickets_page'))
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cur.fetchone()
    
    if ticket and ticket[0] == 'open':
        cur.execute('UPDATE tickets SET status = "in_progress", accepted_by = ?, accepted_by_id = ?, accepted_by_name = ?, accepted_by_avatar = ? WHERE id = ?', 
                    (session['username'], session['user_id'], session['full_name'], session.get('avatar', 'it_avatar1.png'), ticket_id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('tickets_page'))

@app.route('/complete/<int:ticket_id>')
def complete_ticket(ticket_id):
    if 'user_id' not in session or session['role'] not in ['it_specialist', 'admin']:
        return redirect(url_for('tickets_page'))
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT accepted_by, status FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cur.fetchone()
    
    if ticket and ticket[1] == 'in_progress' and ticket[0] == session['username']:
        cur.execute('UPDATE tickets SET status = "closed", resolved_at = CURRENT_TIMESTAMP WHERE id = ?', (ticket_id,))
        conn.commit()
    
    conn.close()
    return redirect(url_for('tickets_page'))

@app.route('/reject/<int:ticket_id>')
def reject_ticket(ticket_id):
    if 'user_id' not in session or session['role'] not in ['it_specialist', 'admin']:
        return redirect(url_for('tickets_page'))
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT status FROM tickets WHERE id = ?", (ticket_id,))
    ticket = cur.fetchone()
    
    if ticket and (ticket[0] == 'open' or ticket[0] == 'in_progress'):
        cur.execute('UPDATE tickets SET status = "rejected", accepted_by = ?, accepted_by_name = ?, accepted_by_avatar = ? WHERE id = ?', 
                    (session['username'], session['full_name'], session.get('avatar', 'it_avatar1.png'), ticket_id))
        conn.commit()
    
    conn.close()
    return redirect(url_for('tickets_page'))

@app.route('/delete/<int:ticket_id>')
def delete_ticket(ticket_id):
    if 'user_id' not in session:
        return redirect(url_for('tickets_page'))
    
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    if session['role'] == 'employee':
        cur.execute("DELETE FROM tickets WHERE id = ? AND created_by = ?", (ticket_id, session['username']))
    elif session['role'] in ['it_specialist', 'admin']:
        cur.execute("DELETE FROM tickets WHERE id = ?", (ticket_id,))
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('tickets_page'))

# ===== ЗАПУСК ДЛЯ RENDER.COM =====
if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    
    print("=" * 60)
    print("🔥 IT HELPDESK ЗАПУЩЕН!")
    print("=" * 60)
    
    init_db()
    
    print("=" * 60)
    print(f"🚀 СЕРВЕР ЗАПУЩЕН на порту {port}!")
    print("📱 Доступен по адресу: http://0.0.0.0:" + str(port))
    print("=" * 60)
    print("🖼️ АВАТАРКИ ПО РОЛЯМ:")
    print("   👨‍💼 Сотрудники (6 аватарок без наушников)")
    print("   🛠️ IT-специалисты (6 аватарок с наушниками)")
    print("=" * 60)
    print("📝 РЕГИСТРАЦИЯ БЕЗ ПОДТВЕРЖДЕНИЯ ПОЧТЫ!")
    print("   ПЕРВЫЙ ПОЛЬЗОВАТЕЛЬ ДОЛЖЕН ЗАРЕГИСТРИРОВАТЬСЯ!")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=port, debug=False)
