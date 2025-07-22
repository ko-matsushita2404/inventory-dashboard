from flask import Flask, render_template, request, redirect, url_for, flash
import os
from supabase import create_client, Client
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# Supabase接続設定 (環境変数から)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

# SECRET_KEYの設定 (環境変数から)
app.secret_key = os.environ.get("SECRET_KEY")

# StreamlitアプリのURL (環境変数から)
STREAMLIT_URL = os.environ.get("STREAMLIT_URL", "#") # デフォルトは'#'

# グローバルなSupabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.context_processor
def inject_global_vars():
    """テンプレート全体で使える変数を登録"""
    return dict(STREAMLIT_URL=STREAMLIT_URL)

@app.route('/')
def index():
    try:
        response = supabase.table('parts').select('*').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        flash(f"データの取得中にエラーが発生しました: {e}")
        items = []
    return render_template('index.html', items=items)

@app.route('/search', methods=['POST'])
def search():
    search_term = request.form.get('search_term')
    if not search_term:
        flash("検索キーワードを入力してください。")
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
            flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。")
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f"検索中にエラーが発生しました: {e}")
        return redirect(url_for('index'))

@app.route('/item/<item_id>')
def item_detail(item_id):
    try:
        item_response = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        
        if not item_response.data:
            flash("指定された部品が見つかりません。")
            return redirect(url_for('index'))
        
        item = item_response.data
        order_slip_no = item.get('order_slip_no')

        related_items = []
        if order_slip_no:
            related_response = supabase.table('parts').select('id, production_no, parts_name, remaining_quantity').eq('order_slip_no', order_slip_no).neq('id', item_id).execute()
            if related_response.data:
                related_items = related_response.data

    except Exception as e:
        flash(f"部品詳細の取得中にエラーが発生しました: {e}")
        return redirect(url_for('index'))

    return render_template('detail.html', 
                           item=item, 
                           related_items=related_items)

@app.route('/map')
def inventory_map():
    """在庫マップ表示ページ"""
    location_items = {}
    location_product_numbers = {}
    try:
        # 保管場所が設定されているアイテムのみを取得
        response = supabase.table('parts').select('id, production_no, storage_location').not_.is_('storage_location', 'null').execute()
        if response.data:
            # location_items の作成: {"場所A": [item1, item2], "場所B": [item3]}
            for item in response.data:
                loc = item['storage_location']
                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)
            
            # location_product_numbers の作成: {"場所A": ["製番1", "製番2"], "場所B": ["製番3"]}
            for loc, items in location_items.items():
                location_product_numbers[loc] = list(set([item['production_no'] for item in items]))

    except Exception as e:
        flash(f"マップデータの取得中にエラーが発生しました: {e}")

    return render_template('map.html', 
                           location_items=location_items, 
                           location_product_numbers=location_product_numbers)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
