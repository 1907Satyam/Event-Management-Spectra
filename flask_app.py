import os
import sqlite3
import csv
import io
from flask import Flask, render_template, request, jsonify, url_for, session, redirect, Response
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURATION ---
app.secret_key = 'Spectra@2026' 

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
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
    
    # Grab category from whichever form was used
    category = request.form.get('category') or request.form.get('aloysian_category') or request.form.get('external_category') or 'N/A'
    
    members = request.form.get('members', 'N/A')
    game_name = request.form.get('gameName', 'N/A')
    
    events = "N/A"
    if reg_type == 'programs':
        # Safely combine events from either free or paid form
        solo_events = request.form.getlist('soloEvents') + request.form.getlist('aloysianSoloEvents') + request.form.getlist('externalSoloEvents')
        group_events = request.form.getlist('groupEvents') + request.form.getlist('aloysianGroupEvents') + request.form.getlist('externalGroupEvents')
        events = ", ".join(solo_events + group_events)

    filename = "No File"
    if 'paymentScreenshot' in request.files:
        file = request.files['paymentScreenshot']
        if file and file.filename != '':
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

    return jsonify({'status': 'success', 'message': f'Registration submitted successfully!'})

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
    
    # Fetch ALL rows for the new unified table
    c.execute("SELECT * FROM registrations ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    
    # --- CALCULATE LIVE STATISTICS ---
    total_registrations = len(rows)
    
    # Count Aloysians vs External
    aloysian_count = sum(1 for row in rows if row['college'] and 'aloysius' in str(row['college']).lower())
    external_count = total_registrations - aloysian_count
    
    # Estimate Revenue (Externals pay based on category/type. Aloysians are free)
    total_revenue = 0
    for row in rows:
        if row['college'] and 'aloysius' not in str(row['college']).lower():
            cat = str(row['category']).lower() if row['category'] else ''
            reg_type = str(row['reg_type']).lower() if row['reg_type'] else ''
            
            if reg_type == 'stalls':
                total_revenue += 1000
            elif 'group' in cat:
                total_revenue += 200
            elif 'solo' in cat:
                total_revenue += 100
            elif reg_type == 'programs': # Fallback for external programs without category
                total_revenue += 100 
                
    return render_template('admin.html', 
                           rows=rows, 
                           total_registrations=total_registrations,
                           aloysian_count=aloysian_count,
                           external_count=external_count,
                           total_revenue=total_revenue)

# --- API ROUTE: DELETE ENTRY ---
@app.route('/delete_entry/<int:id>', methods=['POST'])
def delete_entry(id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    c.execute("DELETE FROM registrations WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# --- API ROUTE: EDIT ENTRY ---
@app.route('/edit_entry/<int:id>', methods=['POST'])
def edit_entry(id):
    if not session.get('logged_in'):
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
        
    data = request.json
    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    
    # Update the specific fields
    c.execute("""
        UPDATE registrations 
        SET name=?, college=?, course=?, semester=?, contact=?, category=?, events=?
        WHERE id=?
    """, (data['name'], data['college'], data['course'], data['semester'], data['contact'], data['category'], data['events'], id))
    
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/export_csv')
def export_csv():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    reg_type = request.args.get('type')
    conn = sqlite3.connect('spectra_registrations.db')
    c = conn.cursor()
    
    if reg_type in ['programs', 'stalls', 'games']:
        c.execute("SELECT * FROM registrations WHERE reg_type=? ORDER BY timestamp DESC", (reg_type,))
        filename = f"spectra_{reg_type}_registrations.csv"
    else:
        c.execute("SELECT * FROM registrations ORDER BY reg_type, timestamp DESC")
        filename = "spectra_ALL_registrations.csv"
        
    rows = c.fetchall()
    col_names = [description[0] for description in c.description]
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(col_names)
    
    # --- THE FIX: Format the data so Excel reads it correctly ---
    contact_idx = col_names.index('contact')
    
    modified_rows = []
    for row in rows:
        row_list = list(row)
        # Wrap the contact value in ="value" to force Excel to treat it as pure text
        if row_list[contact_idx]:
            row_list[contact_idx] = f'="{row_list[contact_idx]}"'
            
        modified_rows.append(row_list)
        
    writer.writerows(modified_rows)
    # ------------------------------------------------------------
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

if __name__ == '__main__':
    app.run(debug=True)