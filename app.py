from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
import os
<<<<<<< HEAD
import datetime
=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a

app = Flask(__name__)

# データベースファイルのパスを環境変数から取得、なければローカルのパスを使用
DATABASE = os.environ.get('DATABASE_URL', 'inventory.db')

<<<<<<< HEAD

=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

<<<<<<< HEAD

=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
def init_db():
    with app.app_context():
        conn = get_db_connection()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_number TEXT NOT NULL,
<<<<<<< HEAD
                item_category TEXT,  -- 新しいカラムを追加
=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
                description TEXT,
                location TEXT,
                status TEXT DEFAULT 'in_warehouse',
                moved_out_to TEXT,
                moved_out_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

<<<<<<< HEAD

=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
@app.route('/')
def index():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items WHERE status = 'in_warehouse'").fetchall()
<<<<<<< HEAD

    # 場所ごとの在庫数を集計
    location_counts = {}
    location_product_numbers_temp = {}  # 一時的に製品番号を格納（重複あり）
    location_items = {}  # ロケーションごとのアイテムリスト

    for item in items:
        location = item['location']
        product_number = item['product_number']

        if location not in location_counts:
            location_counts[location] = 0
        location_counts[location] += 1

        if location not in location_product_numbers_temp:
            location_product_numbers_temp[location] = []
        location_product_numbers_temp[location].append(product_number)

        if location not in location_items:
            location_items[location] = []
        location_items[location].append(dict(item))

    conn.close()

    # location_product_numbersの重複を削除
    location_product_numbers = {}
    for location, numbers in location_product_numbers_temp.items():
        location_product_numbers[location] = sorted(list(set(numbers)))

    # HTMLテンプレートが期待している変数名に合わせる
    return render_template('index.html',
                           items=items,
                           location_counts=location_counts,
                           location_product_numbers=location_product_numbers,
                           location_items=location_items)

=======
    
    # 場所ごとの在庫数を集計
    location_counts = {}
    for item in items:
        if item['location'] not in location_counts:
            location_counts[item['location']] = 0
        location_counts[item['location']] += 1

    conn.close()
    return render_template('index.html', items=items, location_counts=location_counts)
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a

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
<<<<<<< HEAD
                headers = next(csv_reader)  # Skip header row
                for row in csv_reader:
                    # CSV columns: A=Timeline (row[0]), B=Product Number (row[1]), C=Item Category (row[2]), D=Description (row[3]), E=Location (row[4])
                    product_number = row[1] if len(row) > 1 else ''  # 製番
                    item_category = row[2] if len(row) > 2 else ''  # 品目 (新しいカラム)
                    description = row[3] if len(row) > 3 else ''  # 説明
                    location = row[4] if len(row) > 4 else ''  # 保管場所
                    # Check if the exact same item already exists
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT id FROM items WHERE product_number = ? AND item_category = ? AND description = ? AND location = ?",
                        (product_number, item_category, description, location)
                    )
                    existing_item = cursor.fetchone()
                    
                    if not existing_item:
                        conn.execute(
                            "INSERT INTO items (product_number, item_category, description, location) VALUES (?, ?, ?, ?)",
                            (product_number, item_category, description, location)
                        )
                conn.commit()
            conn.close()
            os.remove(filepath)  # Clean up uploaded file
            return redirect(url_for('index'))
    return render_template('upload.html')


=======
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

>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
<<<<<<< HEAD
    if item is None:
        conn.close()
        return "Item not found", 404

    # 同じ製番・保管場所の他のアイテムを取得
    similar_items = conn.execute(
        'SELECT * FROM items WHERE product_number = ? AND location = ? AND id != ?',
        (item['product_number'], item['location'], item_id)
    ).fetchall()

    conn.close()
    return render_template('detail.html', item=item, similar_items=similar_items)

=======
    conn.close()
    if item is None:
        return "Item not found", 404
    return render_template('detail.html', item=item)
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a

@app.route('/move_out/<int:item_id>', methods=['GET', 'POST'])
def move_out(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    if request.method == 'POST':
        moved_out_to = request.form['moved_out_to']
<<<<<<< HEAD
        moved_out_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # SQLの修正：WHERE句にitem_idを追加
=======
        import datetime
        moved_out_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
        conn.execute(
            "UPDATE items SET status = 'moved_out', moved_out_to = ?, moved_out_at = ? WHERE id = ?",
            (moved_out_to, moved_out_at, item_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
<<<<<<< HEAD

    conn.close()
    return render_template('move_out.html', item=item)


=======
    
    conn.close()
    return render_template('move_out.html', item=item)

>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
@app.route('/moved_out_history')
def moved_out_history():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items WHERE status = 'moved_out'").fetchall()
    conn.close()
    return render_template('history.html', items=items)

<<<<<<< HEAD

=======
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
@app.route('/clear_moved_out_history', methods=['POST'])
def clear_moved_out_history():
    conn = get_db_connection()
    conn.execute("DELETE FROM items WHERE status = 'moved_out'")
    conn.commit()
    conn.close()
    return redirect(url_for('moved_out_history'))

<<<<<<< HEAD

# 場所別のアイテム一覧を取得するAPIエンドポイント（オプション）
@app.route('/api/location/<location>')
def get_items_by_location(location):
    conn = get_db_connection()
    items = conn.execute(
        "SELECT * FROM items WHERE location = ? AND status = 'in_warehouse'",
        (location,)
    ).fetchall()
    conn.close()

    items_list = []
    for item in items:
        items_list.append({
            'id': item['id'],
            'product_number': item['product_number'],
            'item_category': item['item_category'],
            'description': item['description'],
            'location': item['location']
        })

    return {'items': items_list}


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
=======
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
