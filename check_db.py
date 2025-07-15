import sqlite3
conn = sqlite3.connect('inventory.db')
conn.text_factory = lambda b: b.decode(errors = 'ignore') # Add this line to handle encoding issues
c = conn.cursor()
c.execute('SELECT DISTINCT location FROM items LIMIT 10')
print(c.fetchall())
conn.close()