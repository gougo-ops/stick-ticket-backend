# 数据库迁移指南：Render → Supabase

## 为什么需要迁移？

Render 免费 PostgreSQL **90天后会过期删除**（你的大约 10月初到期）。  
Supabase 免费 Plan **永久免费**（500MB 存储，够你这个规模长期使用）。

---

## 第 1 步：创建 Supabase 项目

1. 打开 [supabase.com](https://supabase.com)
2. 用 GitHub 登录（免费）
3. 点击 **"New project"**
4. 填写:
   - **Name**: `stick-ticket`
   - **Database Password**: 设置一个强密码并**记下来**
   - **Region**: 选离用户最近的（亚洲选 `ap-southeast-1` Singapore）
   - **Pricing Plan**: **Free**
5. 点击 **"Create project"**，等待 2-3 分钟创建完成

---

## 第 2 步：获取 Supabase 连接串

1. 进入 Supabase Dashboard → 你的项目
2. 左侧菜单 → **Settings** → **Database**
3. 找到 **Connection string** → 选择 **URI**
4. 复制连接串，格式类似：
   ```
   postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```

> ⚠️ **重要**：选择带 `pooler.supabase.com:6543` 的地址（PgBouncer 连接池）

---

## 第 3 步：本地执行备份

你要先从 Render 线上数据库把数据导出来。  
在 Render Dashboard → stick-ticket-api → Shell 中执行，  
或者**在你的电脑上**临时指向 Render 数据库执行：

```bash
# 先获取 Render 数据库的连接串
# Render Dashboard → stick-ticket-api → Environment → DATABASE_URL
# 复制那个连接串

# 设置临时环境变量并备份
cd Desktop/stick-ticket/stick_ticket_backend

# Windows PowerShell:
$env:DATABASE_URL="粘贴Render的DATABASE_URL"
python backup_db.py backup_data.json
```

备份成功后会生成 `backup_data.json`。

---

## 第 4 步：恢复到 Supabase

```bash
# 用 Supabase 连接串恢复
python restore_db.py backup_data.json "postgresql://postgres.xxx:YOUR-PASSWORD@aws-0-xxx.pooler.supabase.com:6543/postgres"

# 验证输出：
# ✅ users: X 条
# ✅ products: X 条
# ✅ orders: X 条
# ✅ ticket_requests: X 条
```

---

## 第 5 步：切换 Render 到 Supabase

1. 打开 [Render Dashboard](https://dashboard.render.com)
2. 进入 **stick-ticket-api** 服务
3. 左侧 **Environment**
4. 修改 **DATABASE_URL** 为你的 Supabase 连接串
5. 点击 **Save Changes** → Render 会自动重启服务
6. 等待 1-2 分钟，访问 `https://stick-ticket.asia/health` 确认正常

> 🔒 等确认一切正常后，可以在 Render Dashboard 删除旧的 `stick-ticket-db` 数据库（避免产生费用）

---

## 将来重新构建 Web App 时的 base href 检查

每次 `flutter build web` 之后，记得修改：
- `web/admin/index.html`: `<base href="/admin/">`
- `web/user/index.html`: `<base href="/app/">`

否则管理端会白屏！
