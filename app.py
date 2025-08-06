import os
import logging
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
from supabase import create_client, Client
from gotrue.errors import AuthApiError
from postgrest.exceptions import APIError
import itertools

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


# --- Custom Jinja2 Filter ---
def flatten_filter(list_of_lists):
    """Flattens a list of lists into a single list."""
    return list(itertools.chain.from_iterable(list_of_lists))

app.jinja_env.filters['flatten'] = flatten_filter


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

def escape_like_term(term: str) -> str:
    """
    Escapes special characters for PostgreSQL LIKE/ILIKE queries and adds wildcards for substring matching.
    The backslash is the escape character in PostgreSQL's standard_conforming_strings.
    """
    if not term:
        return "%%"
    # Escape backslash, then percent, then underscore.
    # The order is important.
    escaped_term = term.replace('\\', '\\\\').replace('%', '\%').replace('_', '\_')
    return f"%{escaped_term}%"


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
        supabase.table('parts').insert({
            'item_id': item_id,
            'production_no': production_no,
            'parts_name': parts_name,
            'action': action,
            'details': details,
        }).execute()
    except Exception as e:
        logging.error(f"Failed to log parts: {e}")


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

# --- Routes ---

@app.route('/')
@login_required
def index():
    """Renders the new home page with usage instructions."""
    return render_template('index.html')


@app.route('/inventory')
@login_required
def inventory():
    """Main page showing parts with a storage location."""
    try:
        response = supabase.table('parts').select('*, order_quantity').not_.is_('storage_location', 'null').neq('storage_location', '').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        logging.error(f"Error fetching parts for inventory page: {e}")
        flash("部品データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('inventory.html', items=items, page_title='保管場所登録済み部品')


@app.route('/all')
@login_required
def all_items():
    """Page showing all parts."""
    try:
        response = supabase.table('parts').select('*, order_quantity').order('created_at', desc=True).limit(100).execute()
        items = response.data or []
    except Exception as e:
        logging.error(f"Error fetching all parts: {e}")
        flash("全部品データの取得中にエラーが発生しました。", "error")
        items = []
    return render_template('all_items.html', items=items, page_title='すべての部品')


@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_item():
    """Page to manually add a new item."""
    if request.method == 'POST':
        try:
            delivery_date_str = request.form.get('delivery_date', '').strip()
            new_part = {
                'production_no': request.form.get('production_no', '').strip(),
                'parts_name': request.form.get('parts_name', '').strip(),
                'parts_no': request.form.get('parts_no', '').strip(),
                'drawing_no': request.form.get('drawing_no', '').strip(),
                'dimensions': request.form.get('dimensions', '').strip(),
                'order_slip_no': request.form.get('order_slip_no', '').strip(),
                
                'delivery_date': delivery_date_str if delivery_date_str else None,
                'storage_location': request.form.get('storage_location', '').strip(),
                'updated_at': datetime.now().isoformat()
            }

            if not new_part['production_no'] or not new_part['parts_name']:
                flash("製番と品名は必須です。", "danger")
                return render_template('add_item.html', item=new_part)

            insert_response = supabase.table('parts').insert(new_part).execute()
            
            inserted_item = insert_response.data[0] if insert_response.data else None

            if not inserted_item:
                flash("データベースへの登録に失敗しました。", "danger")
                return render_template('add_item.html', item=new_part)

            log_work_history(
                item_id=inserted_item['id'],
                production_no=inserted_item['production_no'],
                parts_name=inserted_item['parts_name'],
                action="手動登録",
                details=f"新しい部品「{inserted_item['parts_name']}」が手動で登録されました。"
            )

            flash(f"部品「{inserted_item['parts_name']}」を正常に登録しました。", "success")
            return redirect(url_for('add_item'))

        except APIError as e:
            if e.code == '23505': # Unique violation
                flash("同じ製番、部品番号、発注伝票No、寸法、図番、品名の組み合わせは既に登録されています。", "danger")
            else:
                flash(f"データベースエラーが発生しました: {e.message}", "danger")
            return render_template('add_item.html', item=request.form)
        except Exception as e:
            logging.error(f"Error adding new item: {e}", exc_info=True)
            flash("部品の登録中に予期せぬエラーが発生しました。", "danger")
            return render_template('add_item.html', item=request.form)

    return render_template('add_item.html')


@app.route('/search', methods=['GET', 'POST'])
@login_required
def search():
    """Search results page."""
    search_term = request.form.get('search_term', '').strip() if request.method == 'POST' else request.args.get('search_term', '').strip()
    
    if not search_term:
        flash("検索キーワードを入力してください。", "info")
        return redirect(url_for('inventory'))

    items = search_parts(search_term)
    
    if not items:
        flash(f"キーワード '{search_term}' に一致する部品は見つかりませんでした。", "info")
        # Redirect to inventory but keep the search term in the query for user context
        return redirect(url_for('inventory', search_term=search_term))

    # Always show results on the inventory page template for consistency
    return render_template('inventory.html', items=items, search_term=search_term, page_title=f"'{search_term}' の検索結果")


@app.route('/item/<item_id>')
@login_required
def item_detail(item_id):
    """Displays details for a single part."""
    logging.info(f"Accessing /item/{item_id}")
    try:
        item_response = supabase.table('parts').select('*, order_quantity').eq('id', item_id).single().execute()
        item = item_response.data
        if not item:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('inventory'))

        related_items = []
        order_slip_no = item.get('order_slip_no')
        if order_slip_no:
            logging.info(f"Fetching related items for order slip: {order_slip_no}")
            related_response = supabase.table('parts').select('id, production_no, parts_name').eq('order_slip_no', order_slip_no).neq('id', item_id).execute()
            related_items = related_response.data or []
            logging.info(f"Found {len(related_items)} related items.")

    except Exception as e:
        logging.error(f"Error fetching details for item {item_id}: {e}", exc_info=True)
        flash("部品詳細の取得中にエラーが発生しました。", "error")
        return redirect(url_for('inventory'))

    return render_template('detail.html', item=item, related_items=related_items)


@app.route('/map')
@login_required
def inventory_map_index():
    """Displays the inventory map index page with links to specific areas."""
    return render_template('map_index.html')


@app.route('/map/small_area')
@login_required
def inventory_map_small_area():
    """Displays the small area inventory map."""
    location_items = {}
    location_product_numbers = {}
    small_area_items = {}

    try:
        response = supabase.table('parts').select('id, production_no, storage_location, parts_name, parts_no').not_.is_('storage_location', 'null').neq('storage_location', '').execute()
        if response.data:
            for item in response.data:
                loc = item.get('storage_location')
                if not loc: continue

                if loc.startswith('39') or loc.startswith('40'):
                    if loc not in small_area_items:
                        small_area_items[loc] = []
                    small_area_items[loc].append(item)

                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                prod_nos = {item.get('production_no') for item in items if item.get('production_no')}
                location_product_numbers[loc] = sorted(list(prod_nos))

    except Exception as e:
        logging.error(f"Error fetching data for small area map: {e}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map_small_area.html', 
                           location_items=location_items, 
                           location_product_numbers=location_product_numbers,
                           small_area_items=small_area_items)


@app.route('/map/north_area')
@login_required
def inventory_map_north_area():
    """Displays the north area inventory map."""
    location_items = {}
    location_product_numbers = {}
    north_area_items = {}

    try:
        response = supabase.table('parts').select('id, production_no, storage_location, parts_name, parts_no').not_.is_('storage_location', 'null').neq('storage_location', '').execute()
        if response.data:
            for item in response.data:
                loc = item.get('storage_location')
                if not loc: continue

                if any(loc.startswith(str(n)) for n in range(2, 11)):
                    if loc not in north_area_items:
                        north_area_items[loc] = []
                    north_area_items[loc].append(item)

                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                prod_nos = {item.get('production_no') for item in items if item.get('production_no')}
                location_product_numbers[loc] = sorted(list(prod_nos))

    except Exception as e:
        logging.error(f"Error fetching data for north area map: {e}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map_north_area.html', 
                           location_items=location_items, 
                           location_product_numbers=location_product_numbers,
                           north_area_items=north_area_items)


@app.route('/map/south_area')
@login_required
def inventory_map_south_area():
    """Displays the south area inventory map."""
    location_items = {}
    location_product_numbers = {}
    south_area_items = {}

    try:
        response = supabase.table('parts').select('id, production_no, storage_location, parts_name, parts_no').not_.is_('storage_location', 'null').neq('storage_location', '').execute()
        if response.data:
            for item in response.data:
                loc = item.get('storage_location')
                if not loc: continue

                if any(loc.startswith(str(n)) for n in [34, 33, 22, 23, 24, 25, 26, 27]):
                    if loc not in south_area_items:
                        south_area_items[loc] = []
                    south_area_items[loc].append(item)

                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                prod_nos = {item.get('production_no') for item in items if item.get('production_no')}
                location_product_numbers[loc] = sorted(list(prod_nos))

    except Exception as e:
        logging.error(f"Error fetching data for south area map: {e}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map_south_area.html', 
                           location_items=location_items, 
                           location_product_numbers=location_product_numbers,
                           south_area_items=south_area_items)


@app.route('/map')
@login_required
def inventory_map():
    """Displays the inventory map."""
    location_items = {}
    location_product_numbers = {}
    small_area_items = {}
    north_area_items = {}
    south_area_items = {}

    try:
        response = supabase.table('parts').select('id, production_no, storage_location, parts_name, parts_no').not_.is_('storage_location', 'null').neq('storage_location', '').execute()
        if response.data:
            for item in response.data:
                loc = item.get('storage_location')
                if not loc: continue

                # Classify based on location prefix
                if loc.startswith('39') or loc.startswith('40'):
                    if loc not in small_area_items:
                        small_area_items[loc] = []
                    small_area_items[loc].append(item)
                elif any(loc.startswith(str(n)) for n in range(2, 11)):
                    if loc not in north_area_items:
                        north_area_items[loc] = []
                    north_area_items[loc].append(item)
                elif any(loc.startswith(str(n)) for n in [34, 33, 22, 23, 24, 25, 26, 27]):
                    if loc not in south_area_items:
                        south_area_items[loc] = []
                    south_area_items[loc].append(item)

                # Keep the original logic for the modal
                if loc not in location_items:
                    location_items[loc] = []
                location_items[loc].append(item)

            for loc, items in location_items.items():
                prod_nos = {item.get('production_no') for item in items if item.get('production_no')}
                location_product_numbers[loc] = sorted(list(prod_nos))

    except Exception as e:
        logging.error(f"Error fetching data for inventory map: {e}")
        flash("マップデータの取得中にエラーが発生しました。", "error")

    return render_template('map.html', 
                           location_items=location_items, 
                           location_product_numbers=location_product_numbers,
                           small_area_items=small_area_items,
                           north_area_items=north_area_items,
                           south_area_items=south_area_items)


@app.route('/update', methods=['GET', 'POST'])
@login_required
def search_for_update():
    """Search page for updating items, handles POST search."""
    # URLパラメータから製番を取得（mapからの遷移用）
    production_no_param = request.args.get('production_no', '').strip()
    logging.info(f"Accessing /update. Method: {request.method}, production_no_param: '{production_no_param}'")

    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()
        logging.info(f"POST search_for_update with term: '{search_term}'")
        if not search_term:
            flash("検索キーワードを入力してください。", "info")
            return redirect(url_for('search_for_update'))

        search_results = search_parts(search_term)
        logging.info(f"Found {len(search_results)} results for term '{search_term}'")

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
        logging.info(f"Grouped into {len(unique_order_slips)} unique order slips.")

        if len(unique_order_slips) == 1:
            logging.info(f"Redirecting to update_slip for single slip: {unique_order_slips[0]}")
            return redirect(url_for('update_slip', order_slip_no=unique_order_slips[0]))
        else:
            logging.info("Rendering update_search_results.html for multiple slips.")
            return render_template('update_search_results.html', slips=slips, search_term=search_term)

    # GET request - 製番パラメータがある場合は自動検索
    if production_no_param:
        try:
            logging.info(f"GET request with production_no: '{production_no_param}'")
            # 製番で直接検索
            response = supabase.table('parts').select('*').eq('production_no', production_no_param).execute()
            search_results = response.data or []
            logging.info(f"Found {len(search_results)} results for production_no '{production_no_param}'")

            if not search_results:
                flash(f"製番 '{production_no_param}' の部品が見つかりませんでした。", "info")
                return render_template('update_search.html', initial_search_term=production_no_param)

            # Group results by order_slip_no
            slips = {}
            for item in search_results:
                slip_no = item.get('order_slip_no')
                if slip_no:
                    if slip_no not in slips:
                        slips[slip_no] = []
                    slips[slip_no].append(item)

            unique_order_slips = sorted(slips.keys())
            logging.info(f"Grouped into {len(unique_order_slips)} unique order slips for production_no '{production_no_param}'")

            if len(unique_order_slips) == 1:
                logging.info(f"Redirecting to update_slip for single slip: {unique_order_slips[0]}")
                return redirect(url_for('update_slip', order_slip_no=unique_order_slips[0]))
            elif len(unique_order_slips) > 1:
                logging.info("Rendering update_search_results.html for multiple slips.")
                return render_template('update_search_results.html',
                                        slips=slips,
                                        search_term=production_no_param,
                                        from_production_page=True)
            else: # 0 unique order slips
                logging.warning(f"No order slips found for production_no '{production_no_param}', though parts were found. This might indicate data inconsistency.")
                flash(f"製番 '{production_no_param}' の部品に、更新可能な発注伝票が見つかりませんでした。", "warning")
                return render_template('update_search.html', initial_search_term=production_no_param)

        except Exception as e:
            logging.error(f"Error searching by production_no {production_no_param}: {e}", exc_info=True)
            flash("検索中にエラーが発生しました。", "error")
            # Redirect to the search page with the term pre-filled to avoid a broken state
            return render_template('update_search.html', initial_search_term=production_no_param)

    # Default GET request with no params
    logging.info("Rendering empty update_search.html")
    return render_template('update_search.html', initial_search_term=production_no_param or '')


@app.route('/update/<order_slip_no>', methods=['GET', 'POST'])
@login_required
def update_slip(order_slip_no):
    """Page to update items for a specific order slip."""
    logging.info(f"Accessing /update/{order_slip_no}. Method: {request.method}")
    if request.method == 'POST':
        # ... (rest of the update logic remains complex, refactoring later if needed)
        # For now, just ensuring it uses the global supabase client
        form_data = request.form
        items_to_update = []
        errors = []

        form_data = request.form
        items_to_update = []
        errors = []

        # Fetch all current items for this order slip once
        try:
            logging.info(f"Fetching current items for slip: {order_slip_no}")
            current_items_response = supabase.table('parts').select('*').eq('order_slip_no', order_slip_no).execute()
            current_items_map = {str(item['id']): item for item in current_items_response.data}
            logging.info(f"Found {len(current_items_map)} items for slip: {order_slip_no}")
        except Exception as e:
            logging.error(f"Error fetching current items for update (slip: {order_slip_no}): {e}", exc_info=True)
            flash("現在の部品データの取得中にエラーが発生しました。", "error")
            return redirect(url_for('search_for_update'))

        # Handle bulk storage location update
        bulk_storage_location = form_data.get('bulk_storage_location', '').strip()
        if bulk_storage_location:
            logging.info(f"Bulk storage location provided: '{bulk_storage_location}'")

        for key, value in form_data.items():
            if key.startswith('storage_location_'):
                item_id_str = key.replace('storage_location_', '')
                storage_location = value.strip()

                current_item = current_items_map.get(item_id_str)
                if not current_item:
                    logging.warning(f"Item with ID {item_id_str} not found in current items map.")
                    continue

                original_storage_location = current_item.get('storage_location', '')

                if storage_location != original_storage_location:
                    logging.info(f"Item {item_id_str} queued for update. Location: '{storage_location}'")
                    items_to_update.append({
                        'id': str(item_id_str),
                        'storage_location': storage_location,
                        'current_item': current_item
                    })

        if not items_to_update:
            flash("更新する保管場所が入力されていません。", "info")
            return redirect(url_for('update_slip', order_slip_no=order_slip_no))

        updated_count = 0
        for item_data in items_to_update:
            try:
                current_item = item_data['current_item']
                storage_location = item_data['storage_location']

                if bulk_storage_location:
                    storage_location = bulk_storage_location

                update_payload = {
                    'storage_location': storage_location,
                    'updated_at': datetime.now().isoformat()
                }
                logging.info(f"Updating item {current_item['id']} with payload: {update_payload}")
                update_response = supabase.table('parts').update(update_payload).eq('id', current_item['id']).execute()

                if update_response.data:
                    log_work_history(
                        item_id=current_item['id'],
                        production_no=current_item.get('production_no'),
                        parts_name=current_item.get('parts_name'),
                        action="更新",
                        details=f"保管場所を「{storage_location}」に更新しました。"
                    )
                    updated_count += 1
                else:
                    logging.warning(f"Database update failed for item {current_item['id']}. Response: {update_response}")
                    errors.append(f"部品 '{current_item.get('parts_name')}' のデータベース更新に失敗しました。")

            except Exception as e:
                logging.error(f"Error updating item {item_data['id']}: {e}", exc_info=True)
                errors.append(f"部品ID {item_data['id']} の更新中にエラーが発生しました。")

        if updated_count > 0:
            flash(f"{updated_count}件の部品情報を正常に更新しました。", "success")
        for error in errors:
            flash(error, "danger")

        return redirect(url_for('search_for_update'))

    # GET request
    try:
        logging.info(f"GET request for update_slip: {order_slip_no}")
        response = supabase.table('parts').select('*').eq('order_slip_no', order_slip_no).or_('storage_location.is.null,storage_location.eq.').execute()
        items = response.data
        if not items:
            flash(f"発注伝票No '{order_slip_no}' の部品が見つかりません。", "error")
            return redirect(url_for('search_for_update'))
        logging.info(f"Rendering update_form.html for slip {order_slip_no} with {len(items)} items.")
        return render_template('update_form.html', items=items, order_slip_no=order_slip_no)
    except Exception as e:
        logging.error(f"Error fetching items for update form (slip: {order_slip_no}): {e}", exc_info=True)
        flash("データ取得中にエラーが発生しました。", "error")
        return redirect(url_for('search_for_update'))


@app.route('/delete/<item_id>', methods=['POST'])
@login_required
def delete_item(item_id):
    """Deletes an item."""
    logging.info(f"Attempting to delete item {item_id}")
    try:
        # アイテムを削除する前に、関連情報を取得
        logging.info(f"Fetching info for item {item_id} before deletion.")
        item_response = supabase.table('parts').select('production_no, parts_name, order_slip_no').eq('id', item_id).single().execute()
        item_info = item_response.data
        
        if not item_info:
            flash("削除対象のアイテムが見つかりません。", "error")
            return redirect(url_for('all_items'))

        # 削除実行
        logging.info(f"Executing delete for item {item_id}")
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

        # 削除後の戻り先を改善 - 同じ発注伝票の他の部品がある場合は製番詳細へ
        production_no = item_info.get('production_no')
        if production_no:
            # 同じ製番の他の部品が存在するかチェック
            try:
                logging.info(f"Checking for remaining parts with production_no: {production_no}")
                remaining_response = supabase.table('parts').select('id').eq('production_no', production_no).limit(
                    1).execute()
                if remaining_response.data:
                    logging.info("Remaining parts found. Redirecting to production_details.")
                    return redirect(url_for('production_details', production_no=production_no))
                else:
                    logging.info("No remaining parts found.")
            except Exception as e:
                logging.error(f"Error checking for remaining parts: {e}", exc_info=True)
                pass

    except Exception as e:
        logging.error(f"Error deleting item {item_id}: {e}", exc_info=True)
        flash(f"アイテムの削除中にエラーが発生しました: {e}", "error")
    
    logging.info("Redirecting to all_items after deletion process.")
    return redirect(url_for('all_items'))


@app.route('/production/<production_no>')
@login_required
def production_details(production_no):
    """製番別の詳細表示ページ."""
    logging.info(f"Accessing /production/{production_no}")
    try:
        # 指定された製番の全部品を取得
        response = supabase.table('parts').select('*, order_quantity').eq('production_no', production_no).order('order_slip_no',
                                                                                                desc=False).execute()
        parts = response.data or []
        logging.info(f"Found {len(parts)} parts for production_no '{production_no}'")

        if not parts:
            flash(f"製番 '{production_no}' の部品が見つかりません。", "info")
            return redirect(url_for('inventory_map'))

        # 発注伝票No別にグループ化
        order_slips = {}
        total_parts_count = 0
        unique_locations = set()

        for part in parts:
            order_slip_no = part.get('order_slip_no', '未分類')
            if order_slip_no not in order_slips:
                order_slips[order_slip_no] = []

            order_slips[order_slip_no].append(part)
            total_parts_count += 1

            if part.get('storage_location'):
                unique_locations.add(part.get('storage_location'))
        
        logging.info(f"Grouped into {len(order_slips)} order slips. Total parts: {total_parts_count}")

        # テンプレートに渡すデータ
        return render_template('production_details.html',
                               production_no=production_no,
                               order_slips=order_slips,
                               total_parts_count=total_parts_count,
                               unique_locations=sorted(list(unique_locations)))

    except Exception as e:
        logging.error(f"Error fetching production details for {production_no}: {e}", exc_info=True)
        flash("製番詳細の取得中にエラーが発生しました。", "error")
        return redirect(url_for('inventory_map'))

'''
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
'''

@app.route('/move/<item_id>', methods=['GET', 'POST'])
@login_required
def move_item(item_id):
    """Page to move a specific item."""
    logging.info(f"Accessing /move/{item_id}. Method: {request.method}")
    try:
        item_resp = supabase.table('parts').select('*').eq('id', item_id).single().execute()
        current_item = item_resp.data
        if not current_item:
            flash("指定された部品が見つかりません。", "error")
            return redirect(url_for('search_for_move')) # Assuming this route exists
    except Exception as e:
        logging.error(f"Error fetching item {item_id} for move: {e}", exc_info=True)
        flash("指定された部品の取得に失敗しました。", "error")
        return redirect(url_for('search_for_update')) # Fallback

    if request.method == 'POST':
        new_storage_location = request.form.get('new_storage_location', '').strip()
        logging.info(f"POST to move_item {item_id}. New Location: '{new_storage_location}'")
        
        if not new_storage_location:
            flash("新しい保管場所を入力してください。", "warning")
            return render_template('move_form.html', item=current_item)

        try:
            update_payload = {'storage_location': new_storage_location, 'updated_at': datetime.now().isoformat()}
            logging.info(f"Updating item {item_id} with payload: {update_payload}")
            update_response = supabase.table('parts').update(update_payload).eq('id', item_id).execute()

            if update_response.data:
                log_work_history(
                    item_id=item_id,
                    production_no=current_item.get('production_no'),
                    parts_name=current_item.get('parts_name'),
                    action="移動",
                    details=f"保管場所を「{current_item.get('storage_location')}」から「{new_storage_location}」に移動しました。"
                )
                flash("部品の保管場所を正常に更新しました。", "success")
            else:
                logging.warning(f"Database update failed for move on item {item_id}. Response: {update_response}")
                flash("データベースの更新に失敗した可能性があります。", "warning")

            return redirect(url_for('move_item', item_id=item_id))

        except Exception as e:
            logging.error(f"Error moving item {item_id}: {e}", exc_info=True)
            flash("部品の移動中にエラーが発生しました。", "error")
    
    logging.info(f"Rendering move_form.html for item {item_id}")
    return render_template('move_form.html', item=current_item)


@app.route('/move/location/<location_name>/production/<production_no>', methods=['GET', 'POST'])
@login_required
def move_production_from_location(location_name, production_no):
    """Page to move all parts of a production number from a specific location."""
    if request.method == 'POST':
        new_storage_location = request.form.get('new_storage_location', '').strip()
        if not new_storage_location:
            flash("新しい保管場所を入力してください。", "warning")
            return render_template('move_production.html', location_name=location_name, production_no=production_no)

        try:
            # Find all parts matching the criteria
            response = supabase.table('parts').select('id, parts_name').eq('production_no', production_no).eq('storage_location', location_name).execute()
            items_to_move = response.data or []

            if not items_to_move:
                flash("移動対象の部品が見つかりませんでした。", "warning")
                return redirect(url_for('inventory_map'))

            # Update all found items
            update_payload = {'storage_location': new_storage_location, 'updated_at': datetime.now().isoformat()}
            
            # Update in a batch if possible, otherwise loop
            item_ids = [item['id'] for item in items_to_move]
            update_response = supabase.table('parts').update(update_payload).in_('id', item_ids).execute()

            if update_response.data:
                # Log each move for history
                for item in items_to_move:
                    log_work_history(
                        item_id=item['id'],
                        production_no=production_no,
                        parts_name=item['parts_name'],
                        action="一括移動",
                        details=f"製番 '{production_no}' の一括移動により、保管場所が '{location_name}' から '{new_storage_location}' に変更されました。"
                    )
                flash(f"製番 '{production_no}' の部品 {len(items_to_move)} 点を '{new_storage_location}' へ移動しました。", "success")
            else:
                flash("データベースの更新に失敗しました。", "danger")

            return redirect(url_for('move_production_from_location', location_name=location_name, production_no=production_no))

        except Exception as e:
            logging.error(f"Error during bulk move: {e}", exc_info=True)
            flash("一括移動中にエラーが発生しました。", "danger")

    return render_template('move_production.html', location_name=location_name, production_no=production_no)


@app.route('/move_production_dnd', methods=['POST'])
@login_required
def move_production_dnd():
    """Handles drag and drop move of all parts of a production number from one location to another."""
    data = request.get_json()
    production_no = data.get('production_no')
    original_location = data.get('original_location')
    new_location = data.get('new_location')

    if not production_no or not original_location or not new_location:
        return jsonify({'success': False, 'message': '必要な情報が不足しています。'}), 400

    try:
        # Find all parts matching the criteria
        response = supabase.table('parts').select('id, parts_name').eq('production_no', production_no).eq('storage_location', original_location).execute()
        items_to_move = response.data or []

        if not items_to_move:
            return jsonify({'success': False, 'message': '移動対象の部品が見つかりませんでした。'}), 404

        # Update all found items
        update_payload = {'storage_location': new_location, 'updated_at': datetime.now().isoformat()}
        
        item_ids = [item['id'] for item in items_to_move]
        update_response = supabase.table('parts').update(update_payload).in_('id', item_ids).execute()

        if update_response.data:
            # Log each move for history
            for item in items_to_move:
                log_work_history(
                    item_id=item['id'],
                    production_no=production_no,
                    parts_name=item['parts_name'],
                    action="D&D一括移動",
                    details=f"製番 '{production_no}' のD&D一括移動により、保管場所が '{original_location}' から '{new_location}' に変更されました。"
                )
            return jsonify({'success': True, 'message': f"製番 '{production_no}' の部品 {len(items_to_move)} 点を '{new_location}' へ移動しました。"})
        else:
            return jsonify({'success': False, 'message': 'データベースの更新に失敗しました。'}), 500

    except Exception as e:
        logging.error(f"Error during D&D bulk move: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f"一括移動中にエラーが発生しました: {e}"}), 500


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
