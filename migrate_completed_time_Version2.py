import sqlite3

DB_PATH = '/data/users.db'

conn = sqlite3.connect(DB_PATH)
try:
    conn.execute('ALTER TABLE users ADD COLUMN completed_time TEXT;')
    print("Миграция успешно применена!")
except Exception as e:
    print("Ошибка или поле уже добавлено:", e)
conn.commit()
conn.close()