-- 种子数据：初始商品
-- 在 SQL Editor 中执行（migration 之后）

INSERT INTO public.products (name, image_url, price) VALUES
  ('咖啡', '☕', 5),
  ('蛋糕', '🍰', 15),
  ('盲盒', '🎁', 30),
  ('电影票', '🎬', 50),
  ('图书', '📚', 20);

-- 管理员账户创建方式（三选一）：

-- 方式 1：在 Supabase Dashboard → Authentication → Users → Add User 手动创建
--   Email: admin@stickticket.local
--   Password: 设置安全密码
--   创建后执行：
--   UPDATE public.profiles SET role = 'admin' WHERE username = 'admin';

-- 方式 2：注册普通用户后在 SQL Editor 升级为 admin
--   UPDATE public.profiles SET role = 'admin' WHERE username = '<你的用户名>';

-- 方式 3：直接在 auth.users 和 public.profiles 中插入（需要 Supabase 管理权限）
--   此方式不推荐，因为 Supabase Auth 密码哈希格式复杂
