import sqlite3
conn = sqlite3.connect('inventory.db')
<<<<<<< HEAD
conn.text_factory = lambda b: b.decode(errors = 'ignore')
c = conn.cursor()
c.execute("PRAGMA table_info(items)")
for row in c.fetchall():
    print(row)
=======
conn.text_factory = lambda b: b.decode(errors = 'ignore') # Add this line to handle encoding issues
c = conn.cursor()
c.execute('SELECT DISTINCT location FROM items LIMIT 10')
print(c.fetchall())
>>>>>>> 333b946b7ae5a8209b55c4d4d0194c5a67f5cd8a
conn.close()