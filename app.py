from flask import Flask, render_template, request, redirect, url_for, flash, session
from functools import wraps
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime
import logging

# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# --- App Configuration ---
app.secret_key = os.environ.get("SECRET_KEY")

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_jwt' not in session:
            flash("ログインが必要です。", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ログ設定
logging.basicConfig(level=logging.INFO)

# Supabaseクライアントを生成する関数
def get_supabase_client():
    """リクエストごとに新しいSupabaseクライアントを生成する"""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not supabase_key or not supabase_key.strip():
        app.logger.error("SupabaseのURLまたはキーが環境変数に設定されていません。")
        return None
    return create_client(supabase_url, supabase_key)


def safe_int_convert(value, default=0):
    """安全な整数変換"""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def escape_search_term(term):
    """検索文字列のエスケープ"""
    if not term:
        return ""
    # PostgreSQLのLIKE用特殊文字をエスケープ
    term = term.replace('%', '\%').replace('_', '\_')
    return f"%{term}%"


# === Main Read-Only Routes ===

@app.route('/')
@login_required
def index():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return render_template('index.html', items=[])
    try:
        # storage_locationがNULLでなく、空文字列でもないデータを取得
        response = supabase.table('parts').select('*').not_.is_('storage_location', 'null').neq('storage_location', '').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        app.logger.error(f"データ取得エラー: {str(e)}")
        flash("データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('index.html', items=items, page_title='保管場所登録済み部品')


@app.route('/all')
@login_required
def all_items():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return render_template('all_items.html', items=[])
    try:
        response = supabase.table('parts').select('*').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        app.logger.error(f"データ取得エラー: {str(e)}")
        flash("データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('all_items.html', items=items, page_title='すべての部品')


@app.route('/search', methods=['POST'])
@login_required
def search():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('index'))

    search_term = request.form.get('search_term', '').strip()
    if not search_term:
        flash("検索キーワードを入力してください。", "info")
        return redirect(url_for('index'))

    try:
        def escape_search_term(term):
            # ワイルドカードと安全性を考慮して整形
            escaped = term.replace('%', '').replace('_', '').strip()
            return f"%{escaped}%"

        search_query = escape_search_term(search_term)
        app.logger.info(f"[検索語整形後] search_query = {search_query}")

        # OR条件を "|" 区切りで構成
        or_conditions = ",".join([
            f"production_no.ilike.{search_query}",
            f"parts_no.ilike.{search_query}",
            f"parts_name.ilike.{search_query}",
            f"drawing_no.ilike.{search_query}",
            f"order_slip_no.ilike.{search_query}"
        ])
        app.logger.info(f"[検索条件] or_conditions = {or_conditions}")
        app.logger.info(f"[Supabase Query Debug] Final search query: {search_query}")

        # Supabaseに検索クエリを送信
        response = supabase.table('parts').select('*').or_(
            or_conditions
        ).limit(200).execute()

        # 検索結果に応じて分岐
        if response.data:
            if len(response.data) == 1:
                # 1件だけなら詳細ページへ
                return redirect(url_for('item_detail', item_id=response.data[0]['id']))
            else:
                # 複数件なら一覧表示
                return render_template('index.html', items=response.data, search_term=search_term)
        else:
            # 0件ならメッセージ表示
            flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
            return redirect(url_for('index'))

    except Exception as e:
        app.logger.error(f"検索エラー: {str(e)}")
        flash("検索中にエラーが発生しました。", "error")
        return redirect(url_for('index'))


@app.route('/item/<item_id>')
@login_required
def item_detail(item_id):
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('index'))

    # IDの妥当性チェック
    if not item_id or not str(item_id).isdigit():
        flash("無効なIDです。", "error")
        return redirect(url_for('index'))

    try:
        # single()の代わりに通常のselectを使用
        item_response = supabase.table('parts').select('*').eq('id', item_id).execute()

        if not item_response.data:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('index'))

        item = item_response.data[0]
        order_slip_no = item.get('order_slip_no')

        related_items = []
        if order_slip_no:
            related_response = supabase.table('parts').select('id, production_no, parts_name, remaining_quantity').eq(
                'order_slip_no', order_slip_no).neq('id', item_id).execute()
            if related_response.data:
                related_items = related_response.data

    except Exception as e:
        app.logger.error(f"部品詳細取得エラー: {str(e)}")
        flash("部品詳細の取得中にエラーが発生しました。", "error")
        return redirect(url_for('index'))

    return render_template('detail.html', item=item, related_items=related_items)


@app.route('/map')
@login_required
def inventory_map():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return render_template('map.html', location_items={}, location_product_numbers={})

    location_items = {}
    location_product_numbers = {}
    try:
        response = supabase.table('parts').select('id, production_no, storage_location').not_.is_('storage_location',
                                                                                                  'null').execute()
        if response.data:
            for item in response.data:
                loc = item['storage_location']
                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                location_product_numbers[loc] = list(
                    set([item['production_no'] for item in items if item.get('production_no')]))
    except Exception as e:
        app.logger.error(f"マップデータ取得エラー: {str(e)}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map.html', location_items=location_items, location_product_numbers=location_product_numbers)


# === Data Update (Write) Routes ===

@app.route('/update', methods=['GET', 'POST'])
@login_required
def search_for_update():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('search_for_update'))

    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash("検索キーワードを入力してください。", "info")
            return redirect(url_for('search_for_update'))

        try:
            search_query = escape_search_term(search_term)

            or_conditions = ",".join([
                f"production_no.ilike.{search_query}",
                f"parts_no.ilike.{search_query}",
                f"parts_name.ilike.{search_query}",
                f"drawing_no.ilike.{search_query}",
                f"order_slip_no.ilike.{search_query}"
            ])

            response = supabase.table('parts').select(
                'id, production_no, parts_name, order_slip_no'
            ).or_(or_conditions).limit(200).execute()

            # --- ここからデバッグログ ---
            app.logger.info(f"[Supabase Response] raw response: {response}")
            if hasattr(response, 'data') and response.data:
                app.logger.info(f"[Supabase Response] data received. Count: {len(response.data)}")
            if hasattr(response, 'error') and response.error:
                app.logger.error(f"[Supabase Response] error received: {response.error}")
            # --- ここまでデバッグログ ---

            if response.data:
                # 検索結果からユニークな発注伝票Noを抽出
                unique_order_slips = sorted(
                    list(set([item['order_slip_no'] for item in response.data if item.get('order_slip_no')]))
                )

                if len(unique_order_slips) == 1:
                    # 1件の発注伝票Noに絞り込めた場合は直接更新画面へ
                    return redirect(url_for('update_slip', order_slip_no=unique_order_slips[0]))
                else:
                    # 複数件の発注伝票Noが見つかった場合、または検索が曖昧な場合
                    return render_template('update_search_results.html',
                                           search_results=response.data,
                                           search_term=search_term)
            else:
                flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
                return redirect(url_for('search_for_update'))

        except Exception as e:
            app.logger.error(f"更新用検索エラー: {str(e)}")
            flash("検索中にエラーが発生しました。", "error")
            return redirect(url_for('search_for_update'))

    # GETリクエスト → 検索フォーム表示
    return render_template('update_search.html')


@app.route('/update/<order_slip_no>', methods=['GET', 'POST'])
@login_required
def update_slip(order_slip_no):
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('search_for_update'))

    if request.method == 'POST':
        try:
            form_data = request.form
            items_to_update = []
            errors = []

            # フォームから送信されたデータを解析・検証
            for key, delivered_qty_str in form_data.items():
                if key.startswith('delivered_qty_'):
                    delivered_qty_str = delivered_qty_str.strip()
                    if not delivered_qty_str:
                        continue

                    # 安全な数値変換
                    delivered_qty = safe_int_convert(delivered_qty_str)
                    if delivered_qty < 0:
                        continue

                    item_id = key.split('_')[-1]
                    storage_location = form_data.get(f'storage_location_{item_id}', '').strip()

                    items_to_update.append({
                        'id': item_id,
                        'delivered_qty': delivered_qty,
                        'storage_location': storage_location
                    })

            if not items_to_update:
                flash("更新する数量が入力されていません。", "info")
                return redirect(url_for('update_slip', order_slip_no=order_slip_no))

            # データベース更新処理
            updated_count = 0
            for item_data in items_to_update:
                try:
                    # 現在の部品情報を取得
                    item_resp = supabase.table('parts').select('*').eq('id', item_data['id']).execute()

                    if not item_resp.data:
                        errors.append(f"部品ID {item_data['id']} が見つかりません")
                        continue

                    current_item = item_resp.data[0]
                    previous_quantity = safe_int_convert(current_item.get('remaining_quantity', 0))
                    new_quantity = previous_quantity - item_data['delivered_qty']

                    # 在庫不足チェック
                    if new_quantity < 0:
                        errors.append(
                            f"部品 {current_item.get('parts_name', 'Unknown')} の在庫が不足しています (現在: {previous_quantity}, 納入予定: {item_data['delivered_qty']})")
                        continue

                    # partsテーブルを更新
                    update_response = supabase.table('parts').update({
                        'remaining_quantity': new_quantity,
                        'storage_location': item_data['storage_location'],
                        'updated_at': datetime.now().isoformat()
                    }).eq('id', current_item['id']).execute()

                    if hasattr(update_response, 'error') and update_response.error:
                        errors.append(f"部品ID {item_data['id']} の更新に失敗しました")
                        continue

                    # work_historyテーブルに履歴を記録
                    history_data = {
                        'parts_id': current_item['id'],
                        'production_no': current_item.get('production_no', ''),
                        'parts_no': current_item.get('parts_no', ''),
                        'order_slip_no': order_slip_no,
                        'previous_quantity': previous_quantity,
                        'new_quantity': new_quantity,
                        'previous_delivery_date': current_item.get('delivery_date'),
                        'new_delivery_date': current_item.get('delivery_date'),
                        'storage_location': item_data['storage_location'],
                        'notes': f"[Web更新] 納入数量: {item_data['delivered_qty']}",
                        'updated_by': 'web_user'
                    }

                    history_response = supabase.table('work_history').insert(history_data).execute()
                    if hasattr(history_response, 'error') and history_response.error:
                        app.logger.warning(f"履歴記録に失敗: {history_response.error.message}")

                    updated_count += 1

                except Exception as item_error:
                    app.logger.error(f"部品ID {item_data['id']} 更新エラー: {str(item_error)}")
                    errors.append(f"部品ID {item_data['id']} の処理中にエラーが発生しました")

            # 結果メッセージの表示
            if updated_count > 0:
                flash(f"{updated_count}件の部品情報を正常に更新しました。", "success")

            if errors:
                for error in errors:
                    flash(error, "warning")

            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"データ更新エラー: {str(e)}")
            flash("データ更新中にエラーが発生しました。", "error")
            return redirect(url_for('update_slip', order_slip_no=order_slip_no))

    # GETリクエストの場合
    try:
        response = supabase.table('parts').select('*').eq('order_slip_no', order_slip_no).execute()
        if not response.data:
            flash(f"発注伝票No '{order_slip_no}' の部品が見つかりません。", "error")
            return redirect(url_for('search_for_update'))

        return render_template('update_form.html', items=response.data, order_slip_no=order_slip_no)
    except Exception as e:
        app.logger.error(f"更新フォーム表示エラー: {str(e)}")
        flash("データ取得中にエラーが発生しました。", "error")
        return redirect(url_for('search_for_update'))


@app.route('/delete/<item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('index'))

    try:
        # アイテムを削除
        response = supabase.table('parts').delete().eq('id', item_id).execute()

        if response.data:
            flash("アイテムを削除しました。", "success")
        else:
            flash("アイテムの削除に失敗しました。", "error")

    except Exception as e:
        app.logger.error(f"削除エラー: {str(e)}")
        flash("削除中にエラーが発生しました。", "error")

    return redirect(url_for('index'))


# === Data Move Routes ===

@app.route('/move', methods=['GET', 'POST'])
@login_required
def search_for_move():
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('search_for_move'))

    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash("検索キーワードを入力してください。", "info")
            return redirect(url_for('search_for_move'))

        try:
            search_query = escape_search_term(search_term)
            response = supabase.table('parts').select('*').ilike('production_no', search_query).execute()

            if response.data:
                if len(response.data) == 1:
                    return redirect(url_for('move_item', item_id=response.data[0]['id']))
                else:
                    return render_template('move_search_results.html', search_results=response.data,
                                           search_term=search_term)
            else:
                flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
                return redirect(url_for('search_for_move'))
        except Exception as e:
            app.logger.error(f"移動用検索エラー: {str(e)}")
            flash("検索中にエラーが発生しました。", "error")
            return redirect(url_for('search_for_move'))

    return render_template('move_search.html')


@app.route('/move/<item_id>', methods=['GET', 'POST'])
@login_required
def move_item(item_id):
    supabase = get_supabase_client()
    if not supabase:
        flash("データベース接続に失敗しました。", "error")
        return redirect(url_for('search_for_move'))

    if not item_id or not str(item_id).isdigit():
        flash("無効なIDです。", "error")
        return redirect(url_for('search_for_move'))

    if request.method == 'POST':
        try:
            new_storage_location = request.form.get('new_storage_location', '').strip()
            moved_quantity = safe_int_convert(request.form.get('moved_quantity', 0))
            notes = request.form.get('notes', '').strip()

            # 現在の部品情報を取得
            item_resp = supabase.table('parts').select('*').eq('id', item_id).execute()

            if not item_resp.data:
                flash("指定された部品が見つかりません。", "error")
                return redirect(url_for('search_for_move'))

            current_item = item_resp.data[0]
            previous_quantity = safe_int_convert(current_item.get('remaining_quantity', 0))

            # 移動数量が指定されている場合、残数を減らす
            new_quantity = previous_quantity
            if moved_quantity > 0:
                new_quantity = previous_quantity - moved_quantity
                if new_quantity < 0:
                    flash(
                        f"部品 {current_item.get('parts_name', 'Unknown')} の在庫が不足しています (現在: {previous_quantity}, 移動予定: {moved_quantity})",
                        "warning")
                    return redirect(url_for('move_item', item_id=item_id))

            # partsテーブルを更新
            update_data = {
                'storage_location': new_storage_location,
                'updated_at': datetime.now().isoformat()
            }
            if moved_quantity > 0:
                update_data['remaining_quantity'] = new_quantity

            update_response = supabase.table('parts').update(update_data).eq('id', current_item['id']).execute()

            if hasattr(update_response, 'error') and update_response.error:
                flash(f"部品ID {item_id} の更新に失敗しました: {update_response.error.message}", "error")
                return redirect(url_for('move_item', item_id=item_id))

            # work_historyテーブルに履歴を記録
            history_notes = f"[Web移動] 新しい保管場所: {new_storage_location}"
            if moved_quantity > 0:
                history_notes += f", 移動数量: {moved_quantity}"
            if notes:
                history_notes += f", 備考: {notes}"

            history_data = {
                'parts_id': current_item['id'],
                'production_no': current_item.get('production_no', ''),
                'parts_no': current_item.get('parts_no', ''),
                'order_slip_no': current_item.get('order_slip_no', ''),
                'previous_quantity': previous_quantity,
                'new_quantity': new_quantity,
                'previous_delivery_date': current_item.get('delivery_date'),
                'new_delivery_date': current_item.get('delivery_date'),  # 移動では変更なし
                'storage_location': new_storage_location,
                'notes': history_notes,
                'updated_by': 'web_user_move'
            }

            history_response = supabase.table('work_history').insert(history_data).execute()
            if hasattr(history_response, 'error') and history_response.error:
                app.logger.warning(f"履歴記録に失敗: {history_response.error.message}")

            flash("部品の保管場所を正常に更新しました。", "success")
            return redirect(url_for('index'))

        except Exception as e:
            app.logger.error(f"部品移動エラー: {str(e)}")
            flash("部品移動中にエラーが発生しました。", "error")
            return redirect(url_for('move_item', item_id=item_id))

    # GETリクエストの場合
    try:
        item_response = supabase.table('parts').select('*').eq('id', item_id).execute()
        if not item_response.data:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('search_for_move'))

        item = item_response.data[0]
        return render_template('move_form.html', item=item)
    except Exception as e:
        app.logger.error(f"移動フォーム表示エラー: {str(e)}")
        flash("データ取得中にエラーが発生しました。", "error")
        return redirect(url_for('search_for_move'))



# === Authentication Routes ===

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        supabase = get_supabase_client()

        if not supabase:
            flash("データベース接続に失敗しました。", "error")
            return render_template('register.html')

        try:
            # Supabaseにユーザーを登録
            user_response = supabase.auth.sign_up({"email": email, "password": password})
            
            if user_response.user:
                flash("登録が完了しました。メールアドレスを確認してください。", "success")
                return redirect(url_for('login'))
            else:
                flash(f"登録に失敗しました: {user_response.error.message}", "error")
        except Exception as e:
            app.logger.error(f"ユーザー登録エラー: {str(e)}")
            flash("ユーザー登録中にエラーが発生しました。", "error")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        supabase = get_supabase_client()

        if not supabase:
            flash("データベース接続に失敗しました。", "error")
            return render_template('login.html')

        try:
            # Supabaseでログイン
            user_response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            
            if user_response.user:
                session['user_jwt'] = user_response.session.access_token
                session['user_email'] = user_response.user.email
                flash("ログインしました。", "success")
                return redirect(url_for('index'))
            else:
                flash(f"ログインに失敗しました: {user_response.error.message}", "error")
        except Exception as e:
            app.logger.error(f"ログインエラー: {str(e)}")
            flash("ログイン中にエラーが発生しました。", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    # Supabaseクライアントを生成し、セッションを破棄
    supabase = get_supabase_client()
    if supabase:
        try:
            supabase.auth.sign_out()
        except Exception as e:
            app.logger.warning(f"Supabaseログアウトエラー: {str(e)}")
    
    session.pop('user_jwt', None)
    session.pop('user_email', None)
    flash("ログアウトしました。", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
