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

# グローバルなSupabaseクライアントの初期化
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def index():
    try:
        # 最新の100件を表示
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
        # 複数のカラムを対象に横断検索
        search_query = f"%{search_term}%"
        response = supabase.table('parts').select('*').or_(
            f'production_no.ilike.{search_query}',
            f'parts_no.ilike.{search_query}',
            f'parts_name.ilike.{search_query}',
            f'drawing_no.ilike.{search_query}',
            f'order_slip_no.ilike.{search_query}'
        ).limit(200).execute() # 検索結果の上限を200件に

        if response.data:
            # 検索結果が1件の場合は直接詳細ページへ
            if len(response.data) == 1:
                return redirect(url_for('item_detail', item_id=response.data[0]['id']))
            # 複数件の場合は一覧で表示
            return render_template('index.html', items=response.data, search_term=search_term)
        else:
            flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。")
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f"検索中にエラーが発生しました: {e}")
        return redirect(url_for('index'))

@app.route('/item/<item_id>') # item_idをUUIDとして受け取るためintから変更
def item_detail(item_id):
    try:
        item_response = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        
        if not item_response.data:
            flash("指定された部品が見つかりません。")
            return redirect(url_for('index'))
        
        item = item_response.data
        order_slip_no = item.get('order_slip_no')

        # 同じ発注伝票Noを持つ他の部品 (関連部品) を取得
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

# このルートは詳細ページのロジックに統合されたため、コメントアウトまたは削除
# @app.route('/item_by_production_no/<production_no>/<path:location>')
# def item_by_production_no_and_location(production_no, location):
#     ...

if __name__ == '__main__':
    # Renderが使用するポート番号を環境変数から取得
    port = int(os.environ.get('PORT', 5000))
    # debug=False は本番環境での推奨設定
    app.run(host='0.0.0.0', port=port, debug=False)
