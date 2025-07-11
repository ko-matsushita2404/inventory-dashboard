import streamlit as st
import sqlite3
import pandas as pd

DATABASE = 'inventory.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

st.set_page_config(layout="wide", page_title="在庫状況ダッシュボード")

st.title("在庫状況ダッシュボード")

# --- 在庫マップの表示 --- #
st.header("在庫マップ")

conn = get_db_connection()
in_warehouse_items = conn.execute("SELECT * FROM items WHERE status = 'in_warehouse'").fetchall()

# 場所ごとの在庫数を集計
location_counts = {}
for item in in_warehouse_items:
    location = item['location']
    if location not in location_counts:
        location_counts[location] = 0
    location_counts[location] += 1

conn.close()

# CSSを埋め込み
st.markdown("""
<style>
    .container-map {
        display: flex;
        gap: 20px;
        flex-wrap: wrap;
    }
    .item-area-map {
        background-color: #fff;
        border-radius: 8px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        padding: 20px;
        flex: 1;
        min-width: 300px;
    }

    /* 小エリアのスタイル */
    .small-inventory-map {
        margin-bottom: 20px;
        width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    .small-area-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        background-color: #e9e9e9;
        padding: 10px;
        border-radius: 5px;
    }

    /* 大エリアのスタイル */
    .large-inventory-map {
        display: grid;
        grid-template-columns: 1fr 1fr;
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
        min-height: 80px;
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
</style>
""", unsafe_allow_html=True)

# HTML構造をStreamlitに埋め込み
st.markdown(f"""
<div class="container-map">
    <div class="item-area-map">
        <h3>小エリア在庫マップ</h3>
        <div class="small-inventory-map">
            <div class="small-area-grid">
                <div id="小左1段" class="grid-cell"><span class="zone-name">小左1段</span><span class="item-count">{location_counts.get('小左1段', 0)}</span></div>
                <div id="小右1段" class="grid-cell"><span class="zone-name">小右1段</span><span class="item-count">{location_counts.get('小右1段', 0)}</span></div>
                <div id="小左2段" class="grid-cell"><span class="zone-name">小左2段</span><span class="item-count">{location_counts.get('小左2段', 0)}</span></div>
                <div id="小右2段" class="grid-cell"><span class="zone-name">小右2段</span><span class="item-count">{location_counts.get('小右2段', 0)}</span></div>
                <div id="小左3段" class="grid-cell"><span class="zone-name">小左3段</span><span class="item-count">{location_counts.get('小左3段', 0)}</span></div>
                <div id="小右3段" class="grid-cell"><span class="zone-name">小右3段</span><span class="item-count">{location_counts.get('小右3段', 0)}</span></div>
            </div>
        </div>
    </div>

    <div class="item-area-map">
        <h3>大エリア在庫マップ</h3>
        <div class="large-inventory-map">
            <div class="top-right-grid">
                <div id="大北1-1" class="grid-cell"><span class="zone-name">大北1-1</span><span class="item-count">{location_counts.get('大北1-1', 0)}</span></div>
                <div id="大北2-1" class="grid-cell"><span class="zone-name">大北2-1</span><span class="item-count">{location_counts.get('大北2-1', 0)}</span></div>
                <div id="大北3-1" class="grid-cell"><span class="zone-name">大北3-1</span><span class="item-count">{location_counts.get('大北3-1', 0)}</span></div>
                <div id="大北4-1" class="grid-cell"><span class="zone-name">大北4-1</span><span class="item-count">{location_counts.get('大北4-1', 0)}</span></div>
                <div id="大北5-1" class="grid-cell"><span class="zone-name">大北5-1</span><span class="item-count">{location_counts.get('大北5-1', 0)}</span></div>
                <div id="大北6-1" class="grid-cell"><span class="zone-name">大北6-1</span><span class="item-count">{location_counts.get('大北6-1', 0)}</span></div>
                <div id="大北7-1" class="grid-cell"><span class="zone-name">大北7-1</span><span class="item-count">{location_counts.get('大北7-1', 0)}</span></div>
                <div id="大北8-1" class="grid-cell"><span class="zone-name">大北8-1</span><span class="item-count">{location_counts.get('大北8-1', 0)}</span></div>
                <div id="大北9-1" class="grid-cell"><span class="zone-name">大北9-1</span><span class="item-count">{location_counts.get('大北9-1', 0)}</span></div>

                <div id="大北1-2" class="grid-cell"><span class="zone-name">大北1-2</span><span class="item-count">{location_counts.get('大北1-2', 0)}</span></div>
                <div id="大北2-2" class="grid-cell"><span class="zone-name">大北2-2</span><span class="item-count">{location_counts.get('大北2-2', 0)}</span></div>
                <div id="大北3-2" class="grid-cell"><span class="zone-name">大北3-2</span><span class="item-count">{location_counts.get('大北3-2', 0)}</span></div>
                <div id="大北4-2" class="grid-cell"><span class="zone-name">大北4-2</span><span class="item-count">{location_counts.get('大北4-2', 0)}</span></div>
                <div id="大北5-2" class="grid-cell"><span class="zone-name">大北5-2</span><span class="item-count">{location_counts.get('大北5-2', 0)}</span></div>
                <div id="大北6-2" class="grid-cell"><span class="zone-name">大北6-2</span><span class="item-count">{location_counts.get('大北6-2', 0)}</span></div>
                <div id="大北7-2" class="grid-cell"><span class="zone-name">大北7-2</span><span class="item-count">{location_counts.get('大北7-2', 0)}</span></div>
                <div id="大北8-2" class="grid-cell"><span class="zone-name">大北8-2</span><span class="item-count">{location_counts.get('大北8-2', 0)}</span></div>
                <div id="大北9-2" class="grid-cell"><span class="zone-name">大北9-2</span><span class="item-count">{location_counts.get('大北9-2', 0)}</span></div>

                <div id="大北1-3" class="grid-cell"><span class="zone-name">大北1-3</span><span class="item-count">{location_counts.get('大北1-3', 0)}</span></div>
                <div id="大北2-3" class="grid-cell"><span class="zone-name">大北2-3</span><span class="item-count">{location_counts.get('大北2-3', 0)}</span></div>
                <div id="大北3-3" class="grid-cell"><span class="zone-name">大北3-3</span><span class="item-count">{location_counts.get('大北3-3', 0)}</span></div>
                <div id="大北4-3" class="grid-cell"><span class="zone-name">大北4-3</span><span class="item-count">{location_counts.get('大北4-3', 0)}</span></div>
                <div id="大北5-3" class="grid-cell"><span class="zone-name">大北5-3</span><span class="item-count">{location_counts.get('大北5-3', 0)}</span></div>
                <div id="大北6-3" class="grid-cell"><span class="zone-name">大北6-3</span><span class="item-count">{location_counts.get('大北6-3', 0)}</span></div>
                <div id="大北7-3" class="grid-cell"><span class="zone-name">大北7-3</span><span class="item-count">{location_counts.get('大北7-3', 0)}</span></div>
                <div id="大北8-3" class="grid-cell"><span class="zone-name">大北8-3</span><span class="item-count">{location_counts.get('大北8-3', 0)}</span></div>
                <div id="大北9-3" class="grid-cell"><span class="zone-name">大北9-3</span><span class="item-count">{location_counts.get('大北9-3', 0)}</span></div>
            </div>
            <div class="bottom-right-grid">
                <div id="大南1-1" class="grid-cell"><span class="zone-name">大南1-1</span><span class="item-count">{location_counts.get('大南1-1', 0)}</span></div>
                <div id="大南2-1" class="grid-cell"><span class="zone-name">大南2-1</span><span class="item-count">{location_counts.get('大南2-1', 0)}</span></div>
                <div id="大南3-1" class="grid-cell"><span class="zone-name">大南3-1</span><span class="item-count">{location_counts.get('大南3-1', 0)}</span></div>
                <div id="大南4-1" class="grid-cell"><span class="zone-name">大南4-1</span><span class="item-count">{location_counts.get('大南4-1', 0)}</span></div>
                <div id="大南5-1" class="grid-cell"><span class="zone-name">大南5-1</span><span class="item-count">{location_counts.get('大南5-1', 0)}</span></div>
                <div id="大南6-1" class="grid-cell"><span class="zone-name">大南6-1</span><span class="item-count">{location_counts.get('大南6-1', 0)}</span></div>
                <div id="大南7-1" class="grid-cell"><span class="zone-name">大南7-1</span><span class="item-count">{location_counts.get('大南7-1', 0)}</span></div>
                <div id="大南8-1" class="grid-cell"><span class="zone-name">大南8-1</span><span class="item-count">{location_counts.get('大南8-1', 0)}</span></div>

                <div id="大南1-2" class="grid-cell"><span class="zone-name">大南1-2</span><span class="item-count">{location_counts.get('大南1-2', 0)}</span></div>
                <div id="大南2-2" class="grid-cell"><span class="zone-name">大南2-2</span><span class="item-count">{location_counts.get('大南2-2', 0)}</span></div>
                <div id="大南3-2" class="grid-cell"><span class="zone-name">大南3-2</span><span class="item-count">{location_counts.get('大南3-2', 0)}</span></div>
                <div id="大南4-2" class="grid-cell"><span class="zone-name">大南4-2</span><span class="item-count">{location_counts.get('大南4-2', 0)}</span></div>
                <div id="大南5-2" class="grid-cell"><span class="zone-name">大南5-2</span><span class="item-count">{location_counts.get('大南5-2', 0)}</span></div>
                <div id="大南6-2" class="grid-cell"><span class="zone-name">大南6-2</span><span class="item-count">{location_counts.get('大南6-2', 0)}</span></div>
                <div id="大南7-2" class="grid-cell"><span class="zone-name">大南7-2</span><span class="item-count">{location_counts.get('大南7-2', 0)}</span></div>
                <div id="大南8-2" class="grid-cell"><span class="zone-name">大南8-2</span><span class="item-count">{location_counts.get('大南8-2', 0)}</span></div>

                <div id="大南1-3" class="grid-cell"><span class="zone-name">大南1-3</span><span class="item-count">{location_counts.get('大南1-3', 0)}</span></div>
                <div id="大南2-3" class="grid-cell"><span class="zone-name">大南2-3</span><span class="item-count">{location_counts.get('大南2-3', 0)}</span></div>
                <div id="大南3-3" class="grid-cell"><span class="zone-name">大南3-3</span><span class="item-count">{location_counts.get('大南3-3', 0)}</span></div>
                <div id="大南4-3" class="grid-cell"><span class="zone-name">大南4-3</span><span class="item-count">{location_counts.get('大南4-3', 0)}</span></div>
                <div id="大南5-3" class="grid-cell"><span class="zone-name">大南5-3</span><span class="item-count">{location_counts.get('大南5-3', 0)}</span></div>
                <div id="大南6-3" class="grid-cell"><span class="zone-name">大南6-3</span><span class="item-count">{location_counts.get('大南6-3', 0)}</span></div>
                <div id="大南7-3" class="grid-cell"><span class="zone-name">大南7-3</span><span class="item-count">{location_counts.get('大南7-3', 0)}</span></div>
                <div id="大南8-3" class="grid-cell"><span class="zone-name">大南8-3</span><span class="item-count">{location_counts.get('大南8-3', 0)}</span></div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- 在庫リストの表示 --- #
st.header("倉庫内在庫リスト")
if in_warehouse_items:
    df_in_warehouse = pd.DataFrame(in_warehouse_items, columns=in_warehouse_items[0].keys())
    st.dataframe(df_in_warehouse[['product_number', 'description', 'location']], use_container_width=True)
else:
    st.info("現在、倉庫内に在庫はありません。")

# --- 持ち出し履歴の表示 --- #
st.header("持ち出し履歴")
conn = get_db_connection()
moved_out_items = conn.execute("SELECT * FROM items WHERE status = 'moved_out'").fetchall()
conn.close()

if moved_out_items:
    df_moved_out = pd.DataFrame(moved_out_items, columns=moved_out_items[0].keys())
    st.dataframe(df_moved_out[['product_number', 'description', 'location', 'moved_out_to', 'moved_out_at']], use_container_width=True)
else:
    st.info("持ち出し履歴はありません。")
