import streamlit as st
import sqlite3
import pandas as pd
import re
import os
from streamlit.components.v1 import html

DATABASE = 'inventory.db'

def get_db_connection():
    """データベース接続を取得します。"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# --- Streamlit ページ設定 ---
st.set_page_config(layout="wide", page_title="在庫状況ダッシュボード")
st.title("在庫状況ダッシュボード")

# --- データ取得 ---
try:
    conn = get_db_connection()
    in_warehouse_items_for_display = conn.execute("SELECT product_number, location FROM items WHERE status = 'in_warehouse'").fetchall()
    all_items_for_df = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
except Exception as e:
    st.error(f"データベースエラーが発生しました: {e}")
    st.stop()

# --- 在庫数の集計 (製番表示に変更) ---
location_product_numbers = {}
# HTMLから場所名を抽出するための正規表現 (例: 大北1-1, 小左1段)
pattern = re.compile(r'(大北|大南|小左|小右)[0-9-]+(?=[<"])')

for item in in_warehouse_items_for_display:
    if not item['location'] or not isinstance(item['location'], str):
        continue
    
    matches = pattern.findall(item['location'])
    for match in matches:
        location = next((loc for loc in match if loc), None)
        if location:
            if location not in location_product_numbers:
                location_product_numbers[location] = []
            location_product_numbers[location].append(item['product_number'])

# --- HTMLとCSSの読み込みと結合 ---
try:
    # styles.cssの内容を読み込む
    script_dir = os.path.dirname(__file__)
    css_path = os.path.join(script_dir, "static", "css", "styles.css")
    with open(css_path, "r", encoding="utf-8") as f:
        css_content = f.read()

    # index.htmlの内容を読み込む
    html_path = os.path.join(script_dir, "templates", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        index_html_content = f.read()

except FileNotFoundError as e:
    st.error(f"必要なファイルが見つかりません: {e}. 'static/css/styles.css' または 'templates/index.html' が存在するか確認してください。")
    st.stop()

# Flaskのurl_forを削除し、スタイルシートを直接埋め込む
index_html_content = index_html_content.replace(
    """    <link rel="stylesheet" href="{{ url_for('static', filename='css/styles.css') }}">""",
    f"    <style>{css_content}</style>"
)
# Flaskのurl_forを削除 (JavaScriptの読み込み部分)
index_html_content = index_html_content.replace(
    """    <script src="{{ url_for('static', filename='js/board.js') }}"></script>""",
    "" # JavaScriptはStreamlitのiframe内では直接実行できないため削除
)
# Flaskのurl_forを削除 (ボタンのリンク)
index_html_content = index_html_content.replace("{{ url_for('upload_csv') }}", "#")
index_html_content = index_html_content.replace("{{ url_for('moved_out_history') }}", "#")
index_html_content = index_html_content.replace("{{ url_for('item_detail', item_id=item.id) }}", "#")
index_html_content = index_html_content.replace("{{ url_for('move_out', item_id=item.id) }}", "#")


# 在庫数をHTMLに注入
# index.htmlの各grid-cellにitem-countスパンを追加
def inject_product_numbers_into_html(html_string, product_numbers_dict):
    modified_html = html_string
    for location_name, product_numbers in product_numbers_dict.items():
        product_numbers_str = ", ".join(product_numbers) if product_numbers else ""
        modified_html = modified_html.replace(
            f'<div id="{location_name}" class="grid-cell"><span class="zone-name">{location_name}</span></div>',
            f'<div id="{location_name}" class="grid-cell"><span class="zone-name">{location_name}</span><span class="product-numbers">{product_numbers_str}</span></div>'
        )
    return modified_html

final_html_for_display = inject_product_numbers_into_html(index_html_content, location_product_numbers)

# --- Streamlitでの表示 ---
st.header("在庫マップ")
# st.components.v1.htmlを使用してHTMLをレンダリング
# heightとscrollingは必要に応じて調整
html(final_html_for_display, height=800, scrolling=True)

# StreamlitからHTMLへのメッセージング (クリックイベントの受信)
if "selected_location" not in st.session_state:
    st.session_state.selected_location = None

# HTMLからのメッセージを受信
query_params = st.experimental_get_query_params()
if "location" in query_params:
    st.session_state.selected_location = query_params["location"][0]
    st.experimental_set_query_params() # クエリパラメータをクリア

# --- 詳細在庫リストと持ち出し履歴 (StreamlitのDataFrameを使用) ---
st.header("詳細在庫リスト")

if all_items_for_df:
    df_all_items = pd.DataFrame(all_items_for_df, columns=all_items_for_df[0].keys())
    
    # locationカラムのHTMLをクリーンアップして表示
    def clean_location_for_display(location_html_data):
        if not isinstance(location_html_data, str):
            return ""
        matches = pattern.findall(location_html_data)
        cleaned_locations = []
        for match in matches:
            location = next((loc for loc in match if loc), None)
            if location:
                cleaned_locations.append(location)
        return ", ".join(sorted(list(set(cleaned_locations))))

    df_all_items['location'] = df_all_items['location'].apply(clean_location_for_display)

    # 選択された棚に基づいてフィルタリング
    if st.session_state.selected_location:
        st.subheader(f"選択された棚: {st.session_state.selected_location} の在庫")
        filtered_df = df_all_items[df_all_items['location'].str.contains(st.session_state.selected_location, na=False)]
        if not filtered_df.empty:
            st.dataframe(filtered_df[['product_number', 'item_category', 'description', 'location']], use_container_width=True)
        else:
            st.info(f"'{st.session_state.selected_location}' には在庫がありません。")
    else:
        # デフォルト表示 (倉庫内在庫リストと持ち出し履歴)
        in_warehouse_df = df_all_items[df_all_items['status'] == 'in_warehouse']
        moved_out_df = df_all_items[df_all_items['status'] == 'moved_out'].sort_values(by='moved_out_at', ascending=False)

        with st.expander("倉庫内在庫リスト (全件)"):
            if not in_warehouse_df.empty:
                st.dataframe(in_warehouse_df[['product_number', 'item_category', 'description', 'location']], use_container_width=True)
            else:
                st.info("現在、倉庫内に在庫はありません。")
        
        with st.expander("持ち出し履歴 (全件)"):
            if not moved_out_df.empty:
                st.dataframe(moved_out_df[['product_number', 'item_category', 'description', 'location', 'moved_out_to', 'moved_out_at']], use_container_width=True)
            else:
                st.info("持ち出し履歴はありません。")
else:
    st.info("データベースにアイテムが見つかりません。")

# --- データ更新ボタン ---
if st.button("最新の情報に更新"):
    st.rerun()