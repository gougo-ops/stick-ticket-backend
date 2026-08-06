# 棒棒券 Supabase 迁移设计文档

**日期:** 2026-07-01
**状态:** 已确认
**目标:** 将棒棒券项目后端从本地 FastAPI + SQLite 迁移到 Supabase Cloud，实现无需个人电脑做服务器的架构。

## 1. 整体架构

```
┌──────────────────────┐    ┌──────────────────────┐
│  stick_ticket_app    │    │  stick_ticket_admin   │
│  (Flutter 用户端)     │    │  (Flutter 管理端)       │
└──────┬───────────────┘    └──────┬───────────────┘
       │                           │
       │  supabase_flutter SDK     │
       │                           │
       ▼                           ▼
┌──────────────────────────────────────────────────┐
│                 Supabase Cloud                    │
│  ┌──────────┐  ┌────────────┐  ┌──────────────┐ │
│  │   Auth   │  │ PostgreSQL │  │     Edge      │ │
│  │ (认证)    │  │  (数据库)   │  │  Functions    │ │
│  │          │  │  + RLS     │  │  (业务逻辑)    │ │
│  └──────────┘  └────────────┘  └──────────────┘ │
└──────────────────────────────────────────────────┘
```

- Flutter 用 supabase_flutter SDK 直连 Supabase
- 简单查询（商品列表、订单历史、个人信息）→ SDK 直接查 PostgreSQL
- 敏感操作（购买、审批、增券）→ 调用 Edge Functions 保证事务原子性
- FastAPI 后端完全移除

## 2. 数据库设计

### auth.users（Supabase 自动管理）
存储邮箱、密码哈希、session 等认证信息。由 Supabase Auth 完全管理。

### public.profiles（用户业务数据）
```sql
CREATE TABLE public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username    TEXT UNIQUE NOT NULL,
  role        TEXT NOT NULL DEFAULT 'user',  -- 'user' | 'admin'
  ticket_balance INTEGER NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

### public.products（商品表）
```sql
CREATE TABLE public.products (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  image_url   TEXT,
  price       INTEGER NOT NULL,
  stock       INTEGER NOT NULL DEFAULT -1,   -- -1 = 无限
  is_available BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

### public.orders（订单表）
```sql
CREATE TABLE public.orders (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES public.profiles(id),
  product_id  BIGINT NOT NULL REFERENCES public.products(id),
  price       INTEGER NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

### public.ticket_requests（增券申请表）
```sql
CREATE TABLE public.ticket_requests (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES public.profiles(id),
  amount      INTEGER NOT NULL,
  reason      TEXT,
  status      TEXT NOT NULL DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
  admin_id    UUID REFERENCES public.profiles(id),
  admin_note  TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);
```

### 触发器：新用户自动创建 profile
```sql
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, username, role, ticket_balance)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'username', 'user', 0);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

## 3. RLS 权限策略

| 表 | 操作 | 规则 |
|---|---|---|
| products | SELECT（所有人）| is_available = true 或调用者为 admin |
| products | INSERT/UPDATE/DELETE | 仅 admin |
| profiles | SELECT | 自己的行，admin 可读全部 |
| profiles | UPDATE | 自己的行，admin 可改全部 |
| orders | SELECT | 自己的行（user_id = uid） |
| orders | INSERT | 仅通过 Edge Function |
| ticket_requests | SELECT | 自己的行，admin 可读全部 |
| ticket_requests | INSERT | 通过 Edge Function |
| ticket_requests | UPDATE | 仅 admin（审批） |

## 4. Edge Functions（3个）

### purchase（购买商品）
- **输入:** { product_id: number }
- **流程:** 查商品 → 验证可用 → 原子操作（扣余额 + 建订单 + 减库存）
- **安全:** 从 auth context 获取调用者 uid

### submit-request（提交增券申请）
- **输入:** { amount: number, reason?: string }
- **流程:** 校验 amount > 0 → 创建 ticket_request
- **安全:** 从 auth context 获取调用者 uid

### approve-request（审批增券）
- **输入:** { request_id: number, action: 'approve' | 'reject', admin_note?: string }
- **流程:** 校验 admin 角色 → 查申请状态为 pending → approve 则加余额 → 更新申请状态
- **安全:** 校验调用者 role = 'admin'

## 5. Flutter 端改动

### 新增依赖
- `supabase_flutter` — 替代 dio 做 API 调用和认证

### 移除内容
- `dio` 依赖
- `api_client.dart` — 不再需要手写 HTTP client
- `auth_service.dart` — Supabase SDK 内置认证
- 所有手写 HTTP 调用 → 改用 Supabase SDK 或 Edge Function invoke

### 直接查询（SDK）
```
商品列表:   Supabase.instance.from('products').select().eq('is_available', true)
订单历史:   Supabase.instance.from('orders').select('*, products(name)').eq('user_id', uid)
个人信息:   Supabase.instance.from('profiles').select().eq('id', uid).single()
```

### Edge Function 调用
```
购买:       Supabase.instance.functions.invoke('purchase', body: {'product_id': id})
提交申请:    Supabase.instance.functions.invoke('submit-request', body: {...})
审批:       Supabase.instance.functions.invoke('approve-request', body: {...})
```

### 保留不改
- Provider 层结构
- 页面和 Widget
- go_router 路由

## 6. 迁移步骤

1. **Supabase 项目创建** — 注册 supabase.com，创建项目，获取 URL + anon key
2. **数据库建表** — 在 SQL Editor 中执行建表 + RLS + 触发器脚本
3. **种子数据** — 创建管理员账户，插入初始商品
4. **Edge Functions** — 创建 3 个函数，本地测试后部署
5. **Flutter 集成** — 添加 supabase_flutter SDK，初始化
6. **重构数据层** — 逐个功能：认证 → 商品 → 订单 → 增券 → 管理
7. **测试** — 用户注册、购买、申请、管理员审批
8. **上线** — 用户端和管理端均可随时随地使用

## 7. 安全注意事项

- Edge Functions 使用 service_role key，拥有绕过 RLS 的权限
- 客户端使用 anon key，所有操作受 RLS 限制
- 管理员角色在 profiles.role 中设置，Edge Function 内校验
- 购买操作使用数据库事务保证余额不会被错误扣减
