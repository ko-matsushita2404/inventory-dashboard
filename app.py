from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
import os

app = Flask(__name__)
DATABASE = 'inventory.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with app.app_context():
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_number TEXT NOT NULL,
                description TEXT,
                location TEXT,
                status TEXT DEFAULT 'in_warehouse',
                moved_out_to TEXT,
                moved_out_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

@app.route('/')
def index():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items WHERE status = 'in_warehouse'").fetchall()
    
    # 場所ごとの在庫数を集計
    location_counts = {}
    for item in items:
        if item['location'] not in location_counts:
            location_counts[item['location']] = 0
        location_counts[item['location']] += 1

    conn.close()
    return render_template('index.html', items=items, location_counts=location_counts)

@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    if request.method == 'POST':
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            filepath = os.path.join('uploads', file.filename)
            os.makedirs('uploads', exist_ok=True)
            file.save(filepath)

            conn = get_db_connection()
            with open(filepath, 'r', encoding='utf-8') as f:
                csv_reader = csv.reader(f)
                headers = next(csv_reader) # Skip header row
                for row in csv_reader:
                    # Assuming CSV columns are: product_number, description, location
                    # Adjust indices if your CSV has different order/more columns
                    # CSV columns: A=Timeline, B=Product Number, C=Description, D=Location
                    product_number = row[1] if len(row) > 1 else ''
                    description = row[2] if len(row) > 2 else ''
                    location = row[3] if len(row) > 3 else ''
                    conn.execute(
                        "INSERT INTO items (product_number, description, location) VALUES (?, ?, ?)",
                        (product_number, description, location)
                    )
                conn.commit()
            conn.close()
            os.remove(filepath) # Clean up uploaded file
            return redirect(url_for('index'))
    return render_template('upload.html')

@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    if item is None:
        return "Item not found", 404
    return render_template('detail.html', item=item)

@app.route('/move_out/<int:item_id>', methods=['GET', 'POST'])
def move_out(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    if request.method == 'POST':
        moved_out_to = request.form['moved_out_to']
        import datetime
        moved_out_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute(
            "UPDATE items SET status = 'moved_out', moved_out_to = ?, moved_out_at = ? WHERE id = ?",
            (moved_out_to, moved_out_at, item_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    
    conn.close()
    return render_template('move_out.html', item=item)

@app.route('/moved_out_history')
def moved_out_history():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items WHERE status = 'moved_out'").fetchall()
    conn.close()
    return render_template('history.html', items=items)

@app.route('/clear_moved_out_history', methods=['POST'])
def clear_moved_out_history():
    conn = get_db_connection()
    conn.execute("DELETE FROM items WHERE status = 'moved_out'")
    conn.commit()
    conn.close()
    return redirect(url_for('moved_out_history'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
