import os
import logging
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, g
from supabase import create_client, Client
from gotrue.errors import AuthApiError

# --- Initialization ---

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Flask App Initialization
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise ValueError("No SECRET_KEY set for Flask application")

# Supabase Client Initialization
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_ANON_KEY")
if not supabase_url or not supabase_key:
    raise ValueError("Supabase credentials not found in environment variables")
supabase: Client = create_client(supabase_url, supabase_key)


# --- Decorators & Hooks ---

@app.before_request
def before_request():
    """Set user object in g and supabase auth if logged in."""
    g.user = None
    if 'user_jwt' in session:
        try:
            # Set the auth token for the client for this request
            supabase.postgrest.auth(session['user_jwt'])
            user_info = supabase.auth.get_user(session['user_jwt'])
            g.user = user_info.user
        except AuthApiError as e:
            logging.warning(f"Invalid JWT, clearing session: {e}")
            session.clear() # Clear invalid session
            # After clearing session, reset auth to anon key
            supabase.postgrest.auth(os.environ.get("SUPABASE_ANON_KEY"))
        except Exception as e:
            logging.error(f"Error getting user from JWT: {e}")
            session.clear()
            # After clearing session, reset auth to anon key
            supabase.postgrest.auth(os.environ.get("SUPABASE_ANON_KEY"))
    else:
        # For requests without a logged-in user, ensure we use the anon key
        supabase.postgrest.auth(os.environ.get("SUPABASE_ANON_KEY"))


def login_required(f):
    """Decorator to ensure user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash("このページにアクセスするにはログインが必要です。", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


# --- Helper Functions ---

def safe_int_convert(value, default=None):
    """
    Safely converts a value to an integer.
    Returns the default value (or None) if conversion fails.
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def log_work_history(item_id, production_no, parts_name, action, details):
    """Logs an action to the work_history table."""
    try:
        user_email = g.user.email if g.user else "Unknown"
        supabase.table('work_history').insert({
            'item_id': item_id,
            'production_no': production_no,
            'parts_name': parts_name,
            'action': action,
            'details': details,
            'user_email': user_email
        }).execute()
    except Exception as e:
        logging.error(f"Failed to log work history: {e}")


def search_parts(search_term: str, limit=200):
    """
    Performs a search across multiple fields in the 'parts' table.
    """
    if not search_term:
        return []
    
    search_query = escape_like_term(search_term)
    or_conditions = ",".join([
        f"production_no.ilike.{search_query}",
        f"parts_no.ilike.{search_query}",
        f"parts_name.ilike.{search_query}",
        f"drawing_no.ilike.{search_query}",
        f"order_slip_no.ilike.{search_query}"
    ])

    try:
        response = supabase.table('parts').select('*').or_(or_conditions).limit(limit).execute()
        return response.data or []
    except Exception as e:
        logging.error(f"Database search error for term '{search_term}': {e}")
        flash("検索中にデータベースエラーが発生しました。", "error")
        return []

    try:
        response = supabase.table('parts').select('*').or_(or_conditions).limit(limit).execute()
        return response.data or []
    except Exception as e:
        logging.error(f"Database search error for term '{search_term}': {e}")
        flash("検索中にデータベースエラーが発生しました。", "error")
        return []

# --- Routes ---

@app.route('/')
@login_required
def index():
    """Main page showing parts with a storage location."""
    try:
        response = supabase.table('parts').select('*').not_.is_('storage_location', 'null').neq('storage_location', '').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        logging.error(f"Error fetching parts for index: {e}")
        flash("部品データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('index.html', items=items, page_title='保管場所登録済み部品')


@app.route('/all')
@login_required
def all_items():
    """Page showing all parts."""
    try:
        response = supabase.table('parts').select('*').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        logging.error(f"Error fetching all parts: {e}")
        flash("全部品データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('all_items.html', items=items, page_title='すべての部品')


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    """Search results page."""
    search_term = request.form.get('search_term', '').strip() if request.method == 'POST' else request.args.get('search_term', '').strip()
    
    if not search_term:
        flash("検索キーワードを入力してください。", "info")
        return redirect(url_for('index'))

    items = search_parts(search_term)
    
    if not items:
        flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
        # Redirect to index but keep the search term in the query for user context
        return redirect(url_for('index', search_term=search_term))

    # Always show results on the index page template for consistency
    return render_template('index.html', items=items, search_term=search_term, page_title=f"'{search_term}' の検索結果")


@app.route('/item/<item_id>')
@login_required
def item_detail(item_id):
    """Displays details for a single part."""
    try:
        item_response = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        item = item_response.data
        if not item:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('index'))

        related_items = []
        order_slip_no = item.get('order_slip_no')
        if order_slip_no:
            related_response = supabase.table('parts').select('id, production_no, parts_name, remaining_quantity').eq('order_slip_no', order_slip_no).neq('id', item_id).execute()
            related_items = related_response.data or []

    except Exception as e:
        logging.error(f"Error fetching details for item {item_id}: {e}")
        flash("部品詳細の取得中にエラーが発生しました。", "error")
        return redirect(url_for('index'))

    return render_template('detail.html', item=item, related_items=related_items)


@app.route('/map')
@login_required
def inventory_map():
    """Displays the inventory map."""
    location_items = {}
    location_product_numbers = {}
    try:
        response = supabase.table('parts').select('id, production_no, storage_location').not_.is_('storage_location', 'null').neq('storage_location', '').execute()
        if response.data:
            for item in response.data:
                loc = item.get('storage_location')
                if not loc: continue
                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                prod_nos = {item.get('production_no') for item in items if item.get('production_no')}
                location_product_numbers[loc] = sorted(list(prod_nos))
    except Exception as e:
        logging.error(f"Error fetching data for inventory map: {e}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map.html', location_items=location_items, location_product_numbers=location_product_numbers)


@app.route('/update', methods=['GET', 'POST'])
@login_required
def search_for_update():
    """Search page for updating items, handles POST search."""
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash("検索キーワードを入力してください。", "info")
            return redirect(url_for('search_for_update'))

        search_results = search_parts(search_term)

        if not search_results:
            flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
            return redirect(url_for('search_for_update'))

        # Group results by order_slip_no
        slips = {}
        for item in search_results:
            slip_no = item.get('order_slip_no')
            if slip_no:
                if slip_no not in slips:
                    slips[slip_no] = []
                slips[slip_no].append(item)
        
        unique_order_slips = sorted(slips.keys())

        if len(unique_order_slips) == 1:
            return redirect(url_for('update_slip', order_slip_no=unique_order_slips[0]))
        else:
            # Pass all results for the template to render choices
            return render_template('update_search_results.html', slips=slips, search_term=search_term)

    return render_template('update_search.html')


@app.route('/update/<order_slip_no>', methods=['GET', 'POST'])
@login_required
def update_slip(order_slip_no):
    """Page to update items for a specific order slip."""
    if request.method == 'POST':
        # ... (rest of the update logic remains complex, refactoring later if needed)
        # For now, just ensuring it uses the global supabase client
        form_data = request.form
        items_to_update = []
        errors = []

        for key, delivered_qty_str in form_data.items():
            if key.startswith('delivered_qty_'):
                item_id_str = key.replace('delivered_qty_', '')
                delivered_qty = safe_int_convert(delivered_qty_str.strip(), 0)
                
                if delivered_qty > 0:
                    storage_location = form_data.get(f'storage_location_{item_id_str}', '').strip()
                    items_to_update.append({
                        'id': str(item_id_str),
                        'delivered_qty': delivered_qty,
                        'storage_location': storage_location
                    })
        
        if not items_to_update:
            flash("更新する数量が入力されていません。", "info")
            return redirect(url_for('update_slip', order_slip_no=order_slip_no))

        updated_count = 0
        for item_data in items_to_update:
            try:
                item_resp = supabase.table('parts').select('*').eq('id', item_data['id']).single().execute()
                current_item = item_resp.data
                
                previous_quantity = safe_int_convert(current_item.get('remaining_quantity'), 0)
                new_quantity = previous_quantity - item_data['delivered_qty']

                if new_quantity < 0:
                    errors.append(f"部品 '{current_item.get('parts_name')}' の在庫が不足しています。")
                    continue

                update_payload = {
                    'remaining_quantity': new_quantity,
                    'storage_location': item_data['storage_location'],
                    'updated_at': datetime.now().isoformat()
                }
                update_response = supabase.table('parts').update(update_payload).eq('id', current_item['id']).execute()

                if update_response.data:
                    log_work_history(
                        item_id=current_item['id'],
                        production_no=current_item.get('production_no'),
                        parts_name=current_item.get('parts_name'),
                        action="更新",
                        details=f"数量を{previous_quantity}から{new_quantity}に変更、保管場所を「{item_data['storage_location']}」に更新しました。"
                    )
                    updated_count += 1
                else:
                    errors.append(f"部品 '{current_item.get('parts_name')}' のデータベース更新に失敗しました。")

            except Exception as e:
                logging.error(f"Error updating item {item_data['id']}: {e}")
                errors.append(f"部品ID {item_data['id']} の更新中にエラーが発生しました。")

        if updated_count > 0:
            flash(f"{updated_count}件の部品情報を正常に更新しました。", "success")
        for error in errors:
            flash(error, "danger")

        return redirect(url_for('index'))

    # GET request
    try:
        response = supabase.table('parts').select('*').eq('order_slip_no', order_slip_no).execute()
        items = response.data
        if not items:
            flash(f"発注伝票No '{order_slip_no}' の部品が見つかりません。", "error")
            return redirect(url_for('search_for_update'))
        return render_template('update_form.html', items=items, order_slip_no=order_slip_no)
    except Exception as e:
        logging.error(f"Error fetching items for update form (slip: {order_slip_no}): {e}")
        flash("データ取得中にエラーが発生しました。", "error")
        return redirect(url_for('search_for_update'))


@app.route('/delete/<item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """Deletes an item."""
    try:
        # アイテムを削除する前に、関連情報を取得
        item_response = supabase.table('parts').select('production_no, parts_name').eq('id', item_id).single().execute()
        item_info = item_response.data
        
        if not item_info:
            flash("削除対象のアイテムが見つかりません。", "error")
            return redirect(url_for('all_items'))

        # 削除実行
        supabase.table('parts').delete().eq('id', item_id).execute()

        # 削除が成功したとみなし、作業履歴に記録
        log_work_history(
            item_id=item_id,
            production_no=item_info.get('production_no'),
            parts_name=item_info.get('parts_name'),
            action="削除",
            details=f"アイテム「{item_info.get('parts_name')}」を削除しました。"
        )
        flash("アイテムを削除しました。", "success")

    except Exception as e:
        logging.error(f"Error deleting item {item_id}: {e}")
        flash(f"アイテムの削除中にエラーが発生しました: {e}", "error")
    
    return redirect(url_for('all_items'))


@app.route('/move', methods=['GET', 'POST'])
@login_required
def search_for_move():
    """Search page for moving items."""
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        if not search_term:
            flash("検索キーワードを入力してください。", "info")
            return redirect(url_for('search_for_move'))
        
        # In move, we search only by production_no
        try:
            search_query = escape_like_term(search_term)
            response = supabase.table('parts').select('*').ilike('production_no', search_query).execute()
            search_results = response.data or []
        except Exception as e:
            logging.error(f"Error searching for move with term '{search_term}': {e}")
            flash("検索中にエラーが発生しました。", "error")
            search_results = []

        if not search_results:
            flash(f"製番 '{search_term}' に一致する部品は見つかりませんでした。", "info")
            return redirect(url_for('search_for_move'))
        
        if len(search_results) == 1:
            return redirect(url_for('move_item', item_id=search_results[0]['id']))
        
        return render_template('move_search_results.html', search_results=search_results, search_term=search_term)

    return render_template('move_search.html')


@app.route('/move/<item_id>', methods=['GET', 'POST'])
@login_required
def move_item(item_id):
    """Page to move a specific item."""
    try:
        item_resp = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        current_item = item_resp.data
    except Exception as e:
        logging.error(f"Error fetching item {item_id} for move: {e}")
        flash("指定された部品の取得に失敗しました。", "error")
        return redirect(url_for('search_for_move'))

    if request.method == 'POST':
        new_storage_location = request.form.get('new_storage_location', '').strip()
        moved_quantity = safe_int_convert(request.form.get('moved_quantity'), 0)
        
        if not new_storage_location:
            flash("新しい保管場所を入力してください。", "warning")
            return render_template('move_form.html', item=current_item)

        try:
            update_payload = {'storage_location': new_storage_location, 'updated_at': datetime.now().isoformat()}
            update_response = supabase.table('parts').update(update_payload).eq('id', item_id).execute()

            if update_response.data:
                log_work_history(
                    item_id=item_id,
                    production_no=current_item.get('production_no'),
                    parts_name=current_item.get('parts_name'),
                    action="移動",
                    details=f"保管場所を「{current_item.get('storage_location')}」から「{new_storage_location}」に移動しました。数量: {moved_quantity}"
                )
                flash("部品の保管場所を正常に更新しました。", "success")
            else:
                flash("データベースの更新に失敗した可能性があります。", "warning")

            return redirect(url_for('item_detail', item_id=item_id))

        except Exception as e:
            logging.error(f"Error moving item {item_id}: {e}")
            flash("部品の移動中にエラーが発生しました。", "error")
    
    return render_template('move_form.html', item=current_item)


# --- Authentication Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page."""
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            res = supabase.auth.sign_in_with_password({"email": email, "password": password})
            session['user_jwt'] = res.session.access_token
            flash("ログインしました。", "success")
            return redirect(url_for('index'))
        except AuthApiError as e:
            logging.warning(f"Login failed for {email}: {e.message}")
            flash(f"ログインに失敗しました: {e.message}", "danger")
        except Exception as e:
            logging.error(f"An unexpected error occurred during login: {e}")
            flash("ログイン中に予期せぬエラーが発生しました。", "danger")
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logs the user out."""
    try:
        supabase.auth.sign_out(session['user_jwt'])
    except Exception as e:
        logging.warning(f"Supabase sign out failed, but clearing session anyway: {e}")
    session.clear()
    flash("ログアウトしました。", "info")
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page."""
    if g.user:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        try:
            supabase.auth.sign_up({"email": email, "password": password})
            flash("登録が完了しました。確認メールを送信しましたので、メール内のリンクをクリックして認証を完了してください。", "success")
            return redirect(url_for('login'))
        except AuthApiError as e:
            logging.error(f"Registration failed for {email}: {e.message}")
            flash(f"登録に失敗しました: {e.message}", "danger")
        except Exception as e:
            logging.error(f"An unexpected error occurred during registration: {e}")
            flash("登録中に予期せぬエラーが発生しました。", "danger")
    return render_template('register.html')


# --- Main Execution ---

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    # Use debug=True only in development
    app.run(host='0.0.0.0', port=port, debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true")
