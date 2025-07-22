import streamlit as st
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# .envファイルから環境変数を読み込む
load_dotenv()

# ===== Supabase設定 =====
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY")

# Supabaseクライアントを初期化 (st.cache_resourceで接続を維持)
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ===== ページ設定 =====
st.set_page_config(
    page_title="部品管理 - データ更新",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ===== 状態管理 =====
if 'selected_slip_no' not in st.session_state:
    st.session_state.selected_slip_no = None
if 'selected_items' not in st.session_state:
    st.session_state.selected_items = []

# ===== メイン画面 =====
st.title("📝 部品データ更新・入力")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 発注伝票の検索")
    search_term = st.text_input(
        "製番、部品No、品名、発注伝票Noなどで検索",
        placeholder="例: P2024-001, ABC-123, ORD-001",
        help="入力されたキーワードで部分一致検索します。"
    )

    if search_term:
        try:
            search_query = f"%{search_term}%"
            results = supabase.table('parts').select('*').or_(
                f'production_no.ilike.{search_query}',
                f'parts_no.ilike.{search_query}',
                f'parts_name.ilike.{search_query}',
                f'order_slip_no.ilike.{search_query}'
            ).limit(100).execute()

            if results.data:
                order_slips = {}
                for item in results.data:
                    slip_no = item.get('order_slip_no', "未設定")
                    if slip_no not in order_slips:
                        order_slips[slip_no] = []
                    order_slips[slip_no].append(item)

                st.info(f"{len(results.data)}件の部品が見つかりました。({len(order_slips)}件の発注伝票)")
                
                slip_options = sorted(order_slips.keys())
                selected_slip = st.selectbox(
                    "処理する発注伝票を選択してください",
                    slip_options,
                    index=None, # 初期状態では何も選択しない
                    placeholder="選択..."
                )

                if selected_slip:
                    st.session_state.selected_slip_no = selected_slip
                    st.session_state.selected_items = order_slips[selected_slip]
            else:
                st.warning("該当する部品が見つかりませんでした。")
        except Exception as e:
            st.error(f"❌ 検索エラー: {str(e)}")

with col2:
    if st.session_state.selected_slip_no:
        st.subheader(f"2. 発注伝票No: {st.session_state.selected_slip_no}")
        
        # データフレームで部品一覧を表示
        df = pd.DataFrame(st.session_state.selected_items)[['parts_name', 'parts_no', 'remaining_quantity', 'delivery_date']]
        st.dataframe(df, use_container_width=True)

        st.subheader("3. 更新情報の入力")
        update_mode = st.radio("更新方法", ["個別更新", "一括更新"], horizontal=True)

        with st.form(key='update_form'):
            if update_mode == "一括更新":
                st.markdown("**一括で情報を更新します。**")
                batch_storage_location = st.text_input("保管場所", placeholder="例: A棟-2F-棚3")
                batch_notes = st.text_area("備考", placeholder="一括更新の理由など")
                submitted = st.form_submit_button("📦 一括更新を実行", type="primary")

                if submitted:
                    success_count = 0
                    error_count = 0
                    for item in st.session_state.selected_items:
                        try:
                            # partsテーブルの保管場所を更新
                            supabase.table('parts').update({
                                'storage_location': batch_storage_location,
                                'updated_at': datetime.now().isoformat()
                            }).eq('id', item['id']).execute()

                            # work_historyに記録 (数量の変更はない)
                            history_data = {
                                'parts_id': item['id'], 'production_no': item['production_no'], 'parts_no': item['parts_no'],
                                'order_slip_no': st.session_state.selected_slip_no, 'previous_quantity': item['remaining_quantity'],
                                'new_quantity': item['remaining_quantity'], 'previous_delivery_date': item['delivery_date'],
                                'new_delivery_date': item['delivery_date'], 'storage_location': batch_storage_location,
                                'notes': f"[一括更新] {batch_notes}", 'updated_by': 'field_worker'
                            }
                            supabase.table('work_history').insert(history_data).execute()
                            success_count += 1
                        except Exception as e:
                            st.error(f"❌ {item['parts_no']} の更新エラー: {e}")
                            error_count += 1
                    
                    if success_count > 0: st.success(f"✅ {success_count}件の保管場所を一括更新しました。")
                    if error_count > 0: st.warning(f"⚠️ {error_count}件の更新に失敗しました。")

            else: # 個別更新
                st.markdown("**部品ごとに数量や保管場所を更新します。**")
                part_options = {f"{item['parts_name']} ({item['parts_no']})": item['id'] for item in st.session_state.selected_items}
                selected_part_name = st.selectbox("更新する部品を選択", part_options.keys())
                
                if selected_part_name:
                    item_id = part_options[selected_part_name]
                    item = next((p for p in st.session_state.selected_items if p['id'] == item_id), None)

                    st.write(f"**現在の納入残数: {item['remaining_quantity']}**")
                    delivered_quantity = st.number_input("今回納入された数量", min_value=0, value=0)
                    storage_location = st.text_input("保管場所", value=item.get('storage_location', ""), placeholder="例: A棟-2F-棚3")
                    notes = st.text_area("備考", placeholder="個別更新の理由など")
                    submitted = st.form_submit_button("🔄 個別更新を実行", type="primary")

                    if submitted and delivered_quantity > 0:
                        try:
                            previous_quantity = int(item['remaining_quantity'])
                            new_quantity = previous_quantity - delivered_quantity

                            # partsテーブルの数量と保管場所を更新
                            supabase.table('parts').update({
                                'remaining_quantity': new_quantity,
                                'storage_location': storage_location,
                                'updated_at': datetime.now().isoformat()
                            }).eq('id', item['id']).execute()

                            # work_historyに記録
                            history_data = {
                                'parts_id': item['id'], 'production_no': item['production_no'], 'parts_no': item['parts_no'],
                                'order_slip_no': st.session_state.selected_slip_no, 'previous_quantity': previous_quantity,
                                'new_quantity': new_quantity, 'previous_delivery_date': item['delivery_date'],
                                'new_delivery_date': item['delivery_date'], 'storage_location': storage_location,
                                'notes': f"[個別更新] 納入数量:{delivered_quantity}。{notes}", 'updated_by': 'field_worker'
                            }
                            supabase.table('work_history').insert(history_data).execute()
                            st.success(f"✅ {item['parts_name']} を更新しました。 (残数: {previous_quantity} -> {new_quantity})")
                            st.balloons()
                            # 状態をリフレッシュするために検索結果をクリア
                            st.session_state.selected_slip_no = None
                            st.session_state.selected_items = []
                        except Exception as e:
                            st.error(f"❌ 更新エラー: {e}")
                    elif submitted:
                        st.warning("納入数量を1以上で入力してください。")

    else:
        st.info("左側の検索ボックスから、更新したい部品が含まれる発注伝票を検索してください。")

# フッター
st.markdown("---")
st.markdown("**部品管理システム - データ更新画面**")
if st.button("🔄 ページをリフレッシュ"):
    st.session_state.selected_slip_no = None
    st.session_state.selected_items = []
    st.rerun()
