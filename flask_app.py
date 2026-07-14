import os
import sqlite3
import csv
import io
from flask import Flask, render_template, request, jsonify, url_for, session, redirect, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = 'Spectra@2026' 

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# -----------------------------------------
# DATABASE SETUP
# -----------------------------------------
def init_db():
    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reg_type TEXT,
            name TEXT,
            college TEXT,
            course TEXT,
            semester TEXT,
            contact TEXT,
            category TEXT,
            events TEXT,
            members TEXT,
            game_name TEXT,
            screenshot_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# -----------------------------------------
# PUBLIC ROUTES
# -----------------------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/Program.html')
def registration_page():
    return render_template('Program.html')

@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    reg_type = request.form.get('reg_type')
    name = request.form.get('name')
    college = request.form.get('college')
    course = request.form.get('course')
    semester = request.form.get('semester')
    contact = request.form.get('contact')
    category = request.form.get('category', 'N/A')
    members = request.form.get('members', 'N/A')
    game_name = request.form.get('gameName', 'N/A')
    
    events = "N/A"
    if reg_type == 'programs':
        solo_events = request.form.getlist('soloEvents')
        group_events = request.form.getlist('groupEvents')
        events = ", ".join(solo_events + group_events)

    filename = "No File"
    if 'paymentScreenshot' in request.files:
        file = request.files['paymentScreenshot']
        if file.filename != '':
            filename = secure_filename(file.filename) 
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO registrations 
        (reg_type, name, college, course, semester, contact, category, events, members, game_name, screenshot_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (reg_type, name, college, course, semester, contact, category, events, members, game_name, filename))
    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': f'{reg_type.capitalize()} registration submitted successfully!'})

# -----------------------------------------
# SECURE ADMIN ROUTES
# -----------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        if password and password.strip() == 'Spectra@2026':
            session['logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            error = "Invalid password. Please try again."
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin')
def admin_dashboard():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    conn = sqlite3.connect('spectra_registrations.db')
    conn.row_factory = sqlite3.Row 
    c = conn.cursor()
    
    # Fetch data separated by category
    c.execute("SELECT * FROM registrations WHERE reg_type='programs' ORDER BY timestamp DESC")
    programs = c.fetchall()
    
    c.execute("SELECT * FROM registrations WHERE reg_type='stalls' ORDER BY timestamp DESC")
    stalls = c.fetchall()
    
    c.execute("SELECT * FROM registrations WHERE reg_type='games' ORDER BY timestamp DESC")
    games = c.fetchall()
    
    conn.close()
    
    # Pass them separately to the template
    return render_template('admin.html', programs=programs, stalls=stalls, games=games)

# --- ORGANIZED CSV EXPORT ---
@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    # Check if a specific category was requested
    reg_type = request.args.get('type')
    
    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    
    # Filter the SQL query based on the button clicked
    if reg_type in ['programs', 'stalls', 'games']:
        c.execute("SELECT * FROM registrations WHERE reg_type=? ORDER BY timestamp DESC", (reg_type,))
        filename = f"spectra_{reg_type}_registrations.csv"
    else:
        # If no specific type, download all, but sorted by category so it stays neat!
        c.execute("SELECT * FROM registrations ORDER BY reg_type, timestamp DESC")
        filename = "spectra_ALL_registrations.csv"
        
    rows = c.fetchall()
    col_names = [description[0] for description in c.description]
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(col_names)
    writer.writerows(rows)
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

if __name__ == '__main__':
    app.run(debug=True)