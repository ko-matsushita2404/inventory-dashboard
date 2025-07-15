import streamlit as st
st.write("## これはGeminiによる修正版です - 表示確認用")
import sqlite3
import pandas as pd
import re

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
    in_warehouse_items = conn.execute("SELECT location FROM items WHERE status = 'in_warehouse'").fetchall()
    all_items_for_df = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
except Exception as e:
    st.error(f"データベースエラーが発生しました: {e}")
    st.stop()

# --- 在庫数の集計 ---
location_counts = {}
# HTMLから場所名を抽出するための正規表現 (例: 大北1-1, 小左1段)
# id="大北1-1" または zone-name>大北1-1</span> のようなパターンにマッチ
pattern = re.compile(r'id="([^"]+)"|zone-name">([^<]+)<')

for item in in_warehouse_items:
    if not item['location'] or not isinstance(item['location'], str):
        continue
    
    matches = pattern.findall(item['location'])
    for match in matches:
        location = next((loc for loc in match if loc), None)
        if location:
            location_counts[location] = location_counts.get(location, 0) + 1

# --- CSSスタイル --- (static/css/styles.css と index.html のスタイルを統合)
css_style = """
<style>
    body {
        font-family: Arial, sans-serif;
        margin: 0;
        padding: 0;
        background-color: #f4f4f4;
        color: #333;
    }
    h1, h2 { color: #333; }
    .button-group { margin-top: 20px; margin-bottom: 20px; }
    .button-group a, .button-group button {
        display: inline-block;
        padding: 10px 15px;
        margin-right: 10px;
        background-color: #007bff;
        color: white;
        text-decoration: none;
        border-radius: 5px;
        border: none;
        cursor: pointer;
    }
    .button-group a:hover, .button-group button:hover { background-color: #0056b3; }
    .moved-out-button { background-color: #dc3545; }
    .moved-out-button:hover { background-color: #c82333; }

    .container {
        display: flex;
        padding: 20px;
        gap: 20px;
    }
    .item-area {
        background-color: #fff;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        padding: 20px;
    }
    #shelf-area {
        flex: 3;
    }

    /* 小エリアのスタイル */
    .small-inventory-map {
        margin-bottom: 30px;
        width: 600px; /* 小エリア全体の幅 */
        margin-left: auto;
        margin-right: auto;
    }
    .small-area-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr); /* 2列を維持 */
        gap: 10px;
        background-color: #e9e9e9;
        padding: 10px;
        border-radius: 5px;
    }

    /* 大エリアのスタイル */
    .large-inventory-map {
        display: grid;
        grid-template-columns: 1fr 1fr; /* 大北と大南を横並びにする */
        gap: 20px;
    }
    .large-inventory-map .top-right-grid,
    .large-inventory-map .bottom-right-grid {
        display: grid;
        gap: 10px;
        background-color: #e9e9e9;
        padding: 10px;
        border-radius: 5px;
    }
    .large-inventory-map .top-right-grid {
        grid-template-columns: repeat(9, 1fr);
    }
    .large-inventory-map .bottom-right-grid {
        grid-template-columns: repeat(8, 1fr);
    }

    .grid-cell {
        background-color: #f0f0f0;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 10px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 60px; /* Adjust as needed */
        position: relative;
    }
    .zone-name {
        font-weight: bold;
        color: #555;
        margin-bottom: 5px;
    }
    .item-count {
        font-size: 1.5em;
        font-weight: bold;
        color: #007bff;
    }

    /* 詳細在庫リストのスタイル */
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
    th { background-color: #f2f2f2; }
</style>
"""

# --- HTMLコンテンツの生成 --- (index.html の構造を再現)
html_content = f"""
<div class="container">
    <div id="shelf-area" class="item-area">
        <h2>小エリア在庫マップ</h2>
        <div class="small-inventory-map">
            <div class="small-area-grid">
"""
# 小エリアのグリッドセルを動的に生成
small_area_locations = [
    "小左1段", "小右1段",
    "小左2段", "小右2段",
    "小左3段", "小右3段"
]
for loc_name in small_area_locations:
    count = location_counts.get(loc_name, 0)
    html_content += f"""
                <div id="{loc_name}" class="grid-cell">
                    <span class="zone-name">{loc_name}</span>
                    <span class="item-count">{count}</span>
                </div>
"""
html_content += f"""
            </div>
        </div>

        <h2>大エリア在庫マップ</h2>
        <div class="large-inventory-map">
            <div class="top-right-grid">
"""
# 大北エリアのグリッドセルを動的に生成
for i in range(1, 4):
    for j in range(1, 10):
        loc_name = f"大北{j}-{i}"
        count = location_counts.get(loc_name, 0)
        html_content += f"""
                <div id="{loc_name}" class="grid-cell">
                    <span class="zone-name">{loc_name}</span>
                    <span class="item-count">{count}</span>
                </div>
"""
html_content += f"""
            </div>
            <div class="bottom-right-grid">
"""
# 大南エリアのグリッドセルを動的に生成
for i in range(1, 4):
    for j in range(1, 9):
        loc_name = f"大南{j}-{i}"
        count = location_counts.get(loc_name, 0)
        html_content += f"""
                <div id="{loc_name}" class="grid-cell">
                    <span class="zone-name">{loc_name}</span>
                    <span class="item-count">{count}</span>
                </div>
"""
html_content += f"""
            </div>
        </div>
    </div>
</div>
"""

# --- Streamlitでの表示 ---
st.markdown(css_style, unsafe_allow_html=True)
st.markdown(html_content, unsafe_allow_html=True)

# --- 詳細在庫リストと持ち出し履歴 (StreamlitのDataFrameを使用) ---
st.header("詳細在庫リスト")

if all_items_for_df:
    df_all_items = pd.DataFrame(all_items_for_df, columns=all_items_for_df[0].keys())
    
    # locationカラムのHTMLをクリーンアップして表示
    def clean_location_for_display(location_html):
        if not isinstance(location_html, str):
            return ""
        matches = pattern.findall(location_html)
        cleaned_locations = []
        for match in matches:
            location = next((loc for loc in match if loc), None)
            if location:
                cleaned_locations.append(location)
        return ", ".join(sorted(list(set(cleaned_locations))))

    df_all_items['location'] = df_all_items['location'].apply(clean_location_for_display)

    in_warehouse_df = df_all_items[df_all_items['status'] == 'in_warehouse']
    moved_out_df = df_all_items[df_all_items['status'] == 'moved_out'].sort_values(by='moved_out_at', ascending=False)

    with st.expander("倉庫内在庫リスト"):
        if not in_warehouse_df.empty:
            st.dataframe(in_warehouse_df[['product_number', 'description', 'location']], use_container_width=True)
        else:
            st.info("現在、倉庫内に在庫はありません。")
    
    with st.expander("持ち出し履歴"):
        if not moved_out_df.empty:
            st.dataframe(moved_out_df[['product_number', 'description', 'location', 'moved_out_to', 'moved_out_at']], use_container_width=True)
        else:
            st.info("持ち出し履歴はありません。")
else:
    st.info("データベースにアイテムが見つかりません。")

# --- データ更新ボタン ---
if st.button("最新の情報に更新"):
    st.rerun()