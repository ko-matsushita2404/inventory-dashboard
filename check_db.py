import sqlite3
conn = sqlite3.connect('inventory.db')
conn.text_factory = lambda b: b.decode(errors = 'ignore')
c = conn.cursor()
c.execute("PRAGMA table_info(items)")
for row in c.fetchall():
    print(row)
conn.close()