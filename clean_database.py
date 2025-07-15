import sqlite3
import re

def main():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()

    # 正規表現パターンをより堅牢なものに更新
    # id="大北1-1" または zone-name>大北1-1</span> のようなパターンにマッチ
    pattern = re.compile(r'id="([^"]+)"|zone-name">([^<]+)<')

    cursor.execute("SELECT id, location FROM items")
    rows = cursor.fetchall()

    for row in rows:
        item_id, location_html = row
        
        if location_html:
            # 正規表現にマッチするすべての部分を検索
            matches = pattern.findall(location_html)
            
            # 抽出された場所名を格納するリスト
            cleaned_locations = []
            for match in matches:
                # findallはタプルを返すため、空でない方の要素を選択
                location = next((loc for loc in match if loc), None)
                if location:
                    cleaned_locations.append(location)
            
            # 重複を除き、カンマ区切りの文字列に変換
            if cleaned_locations:
                final_location_str = ", ".join(sorted(list(set(cleaned_locations))))
                
                # データベースを更新
                if final_location_str != location_html:
                    print(f"Updating item {item_id}: '{location_html[:50]}...' -> '{final_location_str}'")
                    cursor.execute("UPDATE items SET location = ? WHERE id = ?", (final_location_str, item_id))

    conn.commit()
    conn.close()
    print("Database cleaning complete.")

if __name__ == '__main__':
    main()