from flask import Flask, render_template, request, redirect, url_for, flash
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# --- App Configuration ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")
app.secret_key = os.environ.get("SECRET_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Main Read-Only Routes ===

@app.route('/')
def index():
    try:
        response = supabase.table('parts').select('*').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        flash(f"データの取得中にエラーが発生しました: {e}", "error")
        items = []
    return render_template('index.html', items=items)

@app.route('/search', methods=['POST'])
def search():
    search_term = request.form.get('search_term')
    if not search_term:
        flash("検索キーワードを入力してください。", "info")
        return redirect(url_for('index'))
    
    try:
        search_query = f"%{search_term}%"
        response = supabase.table('parts').select('*').or_(
            f'production_no.ilike.{search_query}',
            f'parts_no.ilike.{search_query}',
            f'parts_name.ilike.{search_query}',
            f'drawing_no.ilike.{search_query}',
            f'order_slip_no.ilike.{search_query}'
        ).limit(200).execute()

        if response.data:
            if len(response.data) == 1:
                return redirect(url_for('item_detail', item_id=response.data[0]['id']))
            return render_template('index.html', items=response.data, search_term=search_term)
        else:
            flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
            return redirect(url_for('index'))
    except Exception as e:
        flash(f"検索中にエラーが発生しました: {e}", "error")
        return redirect(url_for('index'))

@app.route('/item/<item_id>')
def item_detail(item_id):
    try:
        item_response = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        if not item_response.data:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('index'))
        
        item = item_response.data
        order_slip_no = item.get('order_slip_no')

        related_items = []
        if order_slip_no:
            related_response = supabase.table('parts').select('id, production_no, parts_name, remaining_quantity').eq('order_slip_no', order_slip_no).neq('id', item_id).execute()
            if related_response.data:
                related_items = related_response.data

    except Exception as e:
        flash(f"部品詳細の取得中にエラーが発生しました: {e}", "error")
        return redirect(url_for('index'))

    return render_template('detail.html', item=item, related_items=related_items)

@app.route('/map')
def inventory_map():
    location_items = {}
    location_product_numbers = {}
    try:
        response = supabase.table('parts').select('id, production_no, storage_location').not_.is_('storage_location', 'null').execute()
        if response.data:
            for item in response.data:
                loc = item['storage_location']
                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)
            
            for loc, items in location_items.items():
                location_product_numbers[loc] = list(set([item['production_no'] for item in items]))
    except Exception as e:
        flash(f"マップデータの取得中にエラーが発生しました: {e}", "error")

    return render_template('map.html', location_items=location_items, location_product_numbers=location_product_numbers)


# === Data Update (Write) Routes ===

@app.route('/update', methods=['GET', 'POST'])
def search_for_update():
    if request.method == 'POST':
        slip_no = request.form.get('order_slip_no')
        if not slip_no:
            flash("発注伝票Noを入力してください。", "info")
            return redirect(url_for('search_for_update'))
        
        # Check if slip_no exists
        try:
            response = supabase.table('parts').select('id').eq('order_slip_no', slip_no).limit(1).execute()
            if not response.data:
                flash(f"発注伝票No '{slip_no}' は見つかりませんでした。", "error")
                return redirect(url_for('search_for_update'))
        except Exception as e:
            flash(f"伝票検索中にエラーが発生しました: {e}", "error")
            return redirect(url_for('search_for_update'))

        return redirect(url_for('update_slip', order_slip_no=slip_no))
    
    return render_template('update_search.html')

@app.route('/update/<order_slip_no>', methods=['GET', 'POST'])
def update_slip(order_slip_no):
    if request.method == 'POST':
        try:
            form_data = request.form
            items_to_update = []

            # フォームから送信されたデータを解析
            for key, delivered_qty_str in form_data.items():
                if key.startswith('delivered_qty_'):
                    if not delivered_qty_str or int(delivered_qty_str) == 0:
                        continue # 更新数量が0のものはスキップ

                    item_id = key.split('_')[-1]
                    delivered_qty = int(delivered_qty_str)
                    storage_location = form_data.get(f'storage_location_{item_id}')
                    items_to_update.append({
                        'id': item_id,
                        'delivered_qty': delivered_qty,
                        'storage_location': storage_location
                    })
            
            if not items_to_update:
                flash("更新する数量が入力されていません。", "info")
                return redirect(url_for('update_slip', order_slip_no=order_slip_no))

            # データベース更新処理
            for item_data in items_to_update:
                # 1. 現在の部品情報を取得
                item_resp = supabase.table('parts').select('*').eq('id', item_data['id']).single().execute()
                current_item = item_resp.data
                
                previous_quantity = int(current_item['remaining_quantity'])
                new_quantity = previous_quantity - item_data['delivered_qty']

                # 2. partsテーブルを更新
                supabase.table('parts').update({
                    'remaining_quantity': new_quantity,
                    'storage_location': item_data['storage_location'],
                    'updated_at': datetime.now().isoformat()
                }).eq('id', current_item['id']).execute()

                # 3. work_historyテーブルに履歴を記録
                history_data = {
                    'parts_id': current_item['id'], 'production_no': current_item['production_no'],
                    'parts_no': current_item['parts_no'], 'order_slip_no': order_slip_no,
                    'previous_quantity': previous_quantity, 'new_quantity': new_quantity,
                    'previous_delivery_date': current_item['delivery_date'], 'new_delivery_date': current_item['delivery_date'],
                    'storage_location': item_data['storage_location'],
                    'notes': f"[Web更新] 納入数量: {item_data['delivered_qty']}", 'updated_by': 'web_user'
                }
                supabase.table('work_history').insert(history_data).execute()

            flash(f"{len(items_to_update)}件の部品情報を正常に更新しました。", "success")
            return redirect(url_for('index'))

        except Exception as e:
            flash(f"データ更新中にエラーが発生しました: {e}", "error")
            return redirect(url_for('update_slip', order_slip_no=order_slip_no))

    # GETリクエストの場合
    try:
        response = supabase.table('parts').select('*').eq('order_slip_no', order_slip_no).execute()
        if not response.data:
            flash(f"発注伝票No '{order_slip_no}' の部品が見つかりません。", "error")
            return redirect(url_for('search_for_update'))
        
        return render_template('update_form.html', items=response.data, order_slip_no=order_slip_no)
    except Exception as e:
        flash(f"データ取得中にエラーが発生しました: {e}", "error")
        return redirect(url_for('search_for_update'))


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
