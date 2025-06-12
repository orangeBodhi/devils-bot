import sqlite3

DB_PATH = '/data/users.db'
NEW_DAY = 2

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
cur.execute('UPDATE users SET day=? WHERE day != ?', (NEW_DAY, NEW_DAY))
conn.commit()
conn.close()
print(f"Для всех пользователей теперь day={NEW_DAY} (без сброса прогресса)")