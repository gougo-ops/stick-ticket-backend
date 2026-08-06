"""修改刘图图的密码为 wnn520ltt"""
import bcrypt
import psycopg2

conn = psycopg2.connect(
    host='db.kggyeugjwlmntzxmwfru.supabase.co',
    port=6543,
    user='postgres',
    password='wjy666888',
    dbname='postgres',
    sslmode='require',
    connect_timeout=10,
)
cur = conn.cursor()

# 查看所有用户
cur.execute("SELECT id, username, ticket_balance FROM users ORDER BY id")
print("=== 当前用户 ===")
for r in cur.fetchall():
    print(f"  ID={r[0]}  {r[1]}  ({r[2]} 券)")

# 改密码
pw_hash = bcrypt.hashpw(b"wnn520ltt", bcrypt.gensalt())
cur.execute("UPDATE users SET password_hash = %s WHERE username = %s", (pw_hash.decode(), "刘图图"))
conn.commit()
print(f"\n✅ 刘图图密码已改为 wnn520ltt (影响 {cur.rowcount} 行)")

cur.close()
conn.close()
