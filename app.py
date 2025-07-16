from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import csv
import os
import datetime

app = Flask(__name__)

# データベースファイルのパスを環境変数から取得、なければローカルのパスを使用
DATABASE = os.environ.get('DATABASE_URL', 'inventory.db')


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
                item_category TEXT,  -- 新しいカラムを追加
                description TEXT,
                location TEXT,
                status TEXT DEFAULT 'in_warehouse',
                moved_out_to TEXT,
                moved_out_at TEXT
            )
        ''')
        conn.commit()
        conn.close()

# --- 追加ここから ---
INTERNAL_LOCATIONS_PREFIX = ['大北','大南','小右','小左']

def is_internal_location(location_name):
    return any(location_name.startswith(prefix) for prefix in INTERNAL_LOCATIONS_PREFIX)
# --- 追加ここまで ---

@app.route('/')
def index():
    conn = get_db_connection()
    items = conn.execute("SELECT * FROM items WHERE status = 'in_warehouse'").fetchall()

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


@app.route('/item/<int:item_id>')
def item_detail(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    # 同じ製番・保管場所の他のアイテムを取得
    similar_items = conn.execute(
        'SELECT * FROM items WHERE product_number = ? AND location = ? AND id != ?',
        (item['product_number'], item['location'], item_id)
    ).fetchall()

    # 同じ保管場所にある、現在のアイテムとは異なる製番のユニークなリストを取得（ドロップダウン用）
    unique_product_numbers_in_location = conn.execute(
        "SELECT DISTINCT product_number FROM items WHERE location = ? AND product_number != ? AND status = 'in_warehouse' ORDER BY product_number",
        (item['location'], item['product_number'])
    ).fetchall()

    conn.close()
    return render_template('detail.html', item=item, similar_items=similar_items,
                           unique_product_numbers_in_location=unique_product_numbers_in_location)


@app.route('/move_out/<int:item_id>', methods=['GET', 'POST'])
def move_out(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    if item is None:
        conn.close()
        return "Item not found", 404

    if request.method == 'POST':
        moved_out_to = request.form['moved_out_to']
        moved_out_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if is_internal_location(moved_out_to):
            # 構内移動：ステータスはそのままで location のみ更新
            conn.execute(
                "UPDATE items SET location = ? WHERE id = ?",
                (moved_out_to, item_id)
            )
        else:
            # 構外移動：ステータス更新、履歴記録
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


@app.route('/item_by_product_location/<product_number>/<path:location>')
def item_by_product_location(product_number, location):
    conn = get_db_connection()
    item = conn.execute(
        "SELECT id FROM items WHERE product_number = ? AND location = ? AND status = 'in_warehouse' LIMIT 1",
        (product_number, location)
    ).fetchone()
    conn.close()
    if item:
        return redirect(url_for('item_detail', item_id=item['id']))
    else:
        return "Item not found in this location with this product number", 404


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
