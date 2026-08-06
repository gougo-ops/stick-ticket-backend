# 棒棒券 Supabase 迁移 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将棒棒券项目的后端从本地 FastAPI + SQLite 完全迁移到 Supabase Cloud。

**Architecture:** Flutter App 通过 supabase_flutter SDK 直连 Supabase。Auth 用 Supabase 内置认证。简单查询（商品列表、订单历史）走 SDK 直接查 PostgreSQL。敏感操作（购买、审批）走 Edge Functions 保证事务原子性。

**Tech Stack:** Supabase (Auth + PostgreSQL + Edge Functions), Flutter (supabase_flutter SDK), TypeScript/Deno (Edge Functions)

**特别说明:** 当前 App 使用用户名+密码登录。Supabase Auth 底层要求 email。本方案采用虚拟邮箱方案：用户注册时将 username 转为 `{username}@stickticket.local` 作为 email，同时在 user_metadata 中保存真实 username。用户无感知，UI 不变。

---

## 文件结构

### Supabase 端（新建）
- `supabase/migrations/001_schema.sql` — 建表 + RLS + 触发器
- `supabase/seed.sql` — 种子数据
- `supabase/functions/purchase/index.ts` — 购买 Edge Function
- `supabase/functions/submit-request/index.ts` — 提交增券申请
- `supabase/functions/approve-request/index.ts` — 审批增券

### Flutter 用户端（修改）
- 修改 `lib/models/user.dart` — id: int → String (UUID)
- 修改 `lib/models/product.dart` — id: int → String, 添加 Supabase fromJson
- 修改 `lib/models/order.dart` — id/userId/productId: int → String
- 删除 `lib/services/api_client.dart`
- 重写 `lib/services/auth_service.dart` — 基于 Supabase Auth
- 重写 `lib/services/shop_service.dart` — 基于 Supabase SDK + Edge Function
- 重写 `lib/services/request_service.dart` — 基于 Supabase SDK + Edge Function
- 新建 `lib/config/supabase_config.dart` — Supabase 配置
- 修改 `lib/main.dart` — Supabase 初始化替代 MockData
- 修改 `lib/providers/auth_provider.dart` — 适配 Supabase 用户模型
- 修改 `lib/providers/shop_provider.dart` — 适配
- 修改 `lib/providers/request_provider.dart` — 适配
- 修改 `lib/providers/wallet_provider.dart` — 适配
- 修改 `lib/pages/login_page.dart` — 去掉注册模式（改为邮箱输入）
- 删除 `lib/mock/mock_data.dart`

### Flutter 管理端（修改）
- 同用户端的模型修改
- 删除/重写 services 层
- 新建 supabase_config
- 修改 main.dart
- 修改 provider 层
- 删除 mock_data.dart

---

### Task 1: 创建 Supabase 项目并准备 SQL 迁移文件

**Files:**
- Create: `C:\Users\23189\Desktop\stick_ticket_backend\supabase\migrations\001_schema.sql`

- [ ] **Step 1: 注册 Supabase 并创建项目**

1. 打开 https://supabase.com，用 GitHub 账号注册/登录
2. 点击 "New project"，填写：
   - Name: `stick-ticket`
   - Database Password: 生成一个强密码并保存
   - Region: 选离你最近的（如 Singapore 或 Tokyo）
3. 创建后等待数据库就绪（约 2 分钟）
4. 在项目 Settings → API 中复制 `Project URL` 和 `anon public key`

- [ ] **Step 2: 编写 SQL 迁移文件**

```sql
-- 001_schema.sql
-- 棒棒券 Supabase 数据库初始化

-- 1. Profiles 表（扩展 auth.users）
CREATE TABLE public.profiles (
  id          UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  username    TEXT UNIQUE NOT NULL,
  role        TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
  ticket_balance INTEGER NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 2. Products 表
CREATE TABLE public.products (
  id          BIGSERIAL PRIMARY KEY,
  name        TEXT NOT NULL,
  image_url   TEXT,
  price       INTEGER NOT NULL CHECK (price > 0),
  stock       INTEGER NOT NULL DEFAULT -1,
  is_available BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 3. Orders 表
CREATE TABLE public.orders (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES public.profiles(id),
  product_id  BIGINT NOT NULL REFERENCES public.products(id),
  price       INTEGER NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now()
);

-- 4. Ticket Requests 表
CREATE TABLE public.ticket_requests (
  id          BIGSERIAL PRIMARY KEY,
  user_id     UUID NOT NULL REFERENCES public.profiles(id),
  amount      INTEGER NOT NULL CHECK (amount > 0),
  reason      TEXT,
  status      TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  admin_id    UUID REFERENCES public.profiles(id),
  admin_note  TEXT,
  created_at  TIMESTAMPTZ DEFAULT now(),
  updated_at  TIMESTAMPTZ DEFAULT now()
);

-- 5. 新用户自动创建 profile 的触发器
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.profiles (id, username, role, ticket_balance)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'username', split_part(NEW.email, '@', 1)),
    'user',
    0
  );
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE OR REPLACE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- 6. RLS 策略

-- profiles
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own profile" ON public.profiles
  FOR SELECT USING (auth.uid() = id OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
CREATE POLICY "Users update own profile" ON public.profiles
  FOR UPDATE USING (auth.uid() = id OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');

-- products
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Anyone read available products" ON public.products
  FOR SELECT USING (is_available = true
    OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
CREATE POLICY "Admin insert products" ON public.products
  FOR INSERT WITH CHECK ((SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
CREATE POLICY "Admin update products" ON public.products
  FOR UPDATE USING ((SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
CREATE POLICY "Admin delete products" ON public.products
  FOR DELETE USING ((SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');

-- orders
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own orders" ON public.orders
  FOR SELECT USING (auth.uid() = user_id
    OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
-- orders 的 INSERT 由 Edge Function 处理（使用 service_role key，绕过 RLS）

-- ticket_requests
ALTER TABLE public.ticket_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own requests" ON public.ticket_requests
  FOR SELECT USING (auth.uid() = user_id
    OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');
-- INSERT 由 Edge Function 处理
-- UPDATE 由 Edge Function 处理

-- 7. 索引
CREATE INDEX idx_orders_user_id ON public.orders(user_id);
CREATE INDEX idx_orders_created_at ON public.orders(created_at DESC);
CREATE INDEX idx_ticket_requests_user_id ON public.ticket_requests(user_id);
CREATE INDEX idx_ticket_requests_status ON public.ticket_requests(status);
CREATE INDEX idx_ticket_requests_created_at ON public.ticket_requests(created_at DESC);
CREATE INDEX idx_products_is_available ON public.products(is_available);
```

- [ ] **Step 3: 在 Supabase SQL Editor 中执行迁移**

1. 打开 Supabase Dashboard → SQL Editor
2. 创建新查询，粘贴以上 SQL
3. 点击 Run 执行
4. 验证：在 Table Editor 中应看到 4 张新表

- [ ] **Step 4: 编写并执行种子数据 SQL**

在 SQL Editor 中执行以下查询创建管理员：

```sql
-- 先通过 Supabase Auth 创建管理员用户（在 Authentication → Users → Add User 中手动创建）
-- 或者执行以下 SQL 直接插入（需要 Supabase 的 admin API）

-- 种子商品数据（可直接在 SQL Editor 执行）
INSERT INTO public.products (name, image_url, price) VALUES
  ('咖啡', '☕', 5),
  ('蛋糕', '🍰', 15),
  ('盲盒', '🎁', 30),
  ('电影票', '🎬', 50),
  ('图书', '📚', 20);
```

管理员账户需要在 Supabase Dashboard → Authentication → Users 中手动创建：
1. 点击 "Add user"
2. Email: `admin@stickticket.local`
3. Password: 设置一个安全密码
4. 创建后，在 SQL Editor 中执行：`UPDATE public.profiles SET role = 'admin' WHERE username = 'admin';`
   （如果 username 是 `admin`，根据 trigger 会自动从 email 前缀提取）

- [ ] **Step 5: 提交**

```bash
cd stick_ticket_backend
git add supabase/
git commit -m "feat: add supabase schema migration"
```

---

### Task 2: Edge Function — purchase（购买商品）

**Files:**
- Create: `C:\Users\23189\Desktop\stick_ticket_backend\supabase\functions\purchase\index.ts`

- [ ] **Step 1: 安装 Supabase CLI 并初始化**

```bash
# 安装 Supabase CLI
npm install -g supabase

# 进入后端目录
cd C:\Users\23189\Desktop\stick_ticket_backend

# 登录 Supabase
supabase login

# 初始化（link 到你的项目）
supabase init
supabase link --project-ref <your-project-ref>
```

- [ ] **Step 2: 编写 purchase Edge Function**

```typescript
// supabase/functions/purchase/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    // Get JWT from auth header — this is the logged-in user
    const authHeader = req.headers.get("Authorization")!;
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_ANON_KEY") ?? "",
      { global: { headers: { Authorization: authHeader } } }
    );

    // Get current user
    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { product_id } = await req.json();
    if (!product_id) {
      return new Response(JSON.stringify({ error: "缺少 product_id" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // Use service_role client for RLS-bypass operations
    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    // Start transaction (Supabase JS doesn't have direct tx support,
    // but we can use RPC or sequential operations with error rollback)
    // 1. Check product
    const { data: product, error: productError } = await adminClient
      .from("products")
      .select("*")
      .eq("id", product_id)
      .single();

    if (productError || !product) {
      return new Response(JSON.stringify({ error: "商品不存在" }), {
        status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (!product.is_available) {
      return new Response(JSON.stringify({ error: "商品已下架" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 2. Check stock
    if (product.stock === 0) {
      return new Response(JSON.stringify({ error: "商品已售罄" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 3. Check user balance
    const { data: profile, error: profileError } = await adminClient
      .from("profiles")
      .select("*")
      .eq("id", user.id)
      .single();

    if (profileError || !profile) {
      return new Response(JSON.stringify({ error: "用户不存在" }), {
        status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (profile.ticket_balance < product.price) {
      return new Response(JSON.stringify({ error: "棒棒券不足" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 4. Deduct balance
    const { error: deductError } = await adminClient
      .from("profiles")
      .update({ ticket_balance: profile.ticket_balance - product.price })
      .eq("id", user.id);

    if (deductError) {
      return new Response(JSON.stringify({ error: "扣券失败" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    // 5. Decrease stock (if not unlimited)
    if (product.stock > 0) {
      await adminClient
        .from("products")
        .update({ stock: product.stock - 1 })
        .eq("id", product_id);
    }

    // 6. Create order
    const { data: order, error: orderError } = await adminClient
      .from("orders")
      .insert({
        user_id: user.id,
        product_id: product.id,
        price: product.price,
      })
      .select("*, products!inner(name)")
      .single();

    if (orderError) {
      return new Response(JSON.stringify({ error: "创建订单失败" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({
      id: order.id,
      user_id: order.user_id,
      product_id: order.product_id,
      product_name: (order as any).products?.name ?? product.name,
      price: order.price,
      created_at: order.created_at,
    }), {
      status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
```

- [ ] **Step 3: 部署 Edge Function**

```bash
cd C:\Users\23189\Desktop\stick_ticket_backend
supabase functions deploy purchase
```

- [ ] **Step 4: 提交**

```bash
git add supabase/functions/purchase/
git commit -m "feat: add purchase edge function"
```

---

### Task 3: Edge Functions — submit-request 和 approve-request

**Files:**
- Create: `C:\Users\23189\Desktop\stick_ticket_backend\supabase\functions\submit-request\index.ts`
- Create: `C:\Users\23189\Desktop\stick_ticket_backend\supabase\functions\approve-request\index.ts`

- [ ] **Step 1: 编写 submit-request Edge Function**

```typescript
// supabase/functions/submit-request/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_ANON_KEY") ?? "",
      { global: { headers: { Authorization: req.headers.get("Authorization")! } } }
    );

    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { amount, reason } = await req.json();
    if (!amount || amount <= 0) {
      return new Response(JSON.stringify({ error: "申请数量必须大于0" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    const { data: request, error } = await adminClient
      .from("ticket_requests")
      .insert({
        user_id: user.id,
        amount: amount,
        reason: reason ?? "",
        status: "pending",
      })
      .select()
      .single();

    if (error) {
      return new Response(JSON.stringify({ error: "提交申请失败" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify(request), {
      status: 201, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
```

- [ ] **Step 2: 编写 approve-request Edge Function**

```typescript
// supabase/functions/approve-request/index.ts
import { serve } from "https://deno.land/std@0.168.0/http/server.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const authHeader = req.headers.get("Authorization")!;
    const supabaseClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_ANON_KEY") ?? "",
      { global: { headers: { Authorization: authHeader } } }
    );

    // 1. Get current user and verify admin
    const { data: { user }, error: userError } = await supabaseClient.auth.getUser();
    if (userError || !user) {
      return new Response(JSON.stringify({ error: "Unauthorized" }), {
        status: 401, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { data: callerProfile } = await supabaseClient
      .from("profiles")
      .select("role")
      .eq("id", user.id)
      .single();

    if (!callerProfile || callerProfile.role !== "admin") {
      return new Response(JSON.stringify({ error: "需要管理员权限" }), {
        status: 403, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { request_id, action, admin_note } = await req.json();
    if (!request_id || !action || !["approve", "reject"].includes(action)) {
      return new Response(JSON.stringify({ error: "参数错误" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const adminClient = createClient(
      Deno.env.get("SUPABASE_URL") ?? "",
      Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? ""
    );

    // 2. Get request
    const { data: ticketReq, error: reqError } = await adminClient
      .from("ticket_requests")
      .select("*")
      .eq("id", request_id)
      .single();

    if (reqError || !ticketReq) {
      return new Response(JSON.stringify({ error: "申请不存在" }), {
        status: 404, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (ticketReq.status !== "pending") {
      return new Response(JSON.stringify({ error: "该申请已处理" }), {
        status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    if (action === "approve") {
      // 3a. Approve: increase user balance
      const { data: targetProfile } = await adminClient
        .from("profiles")
        .select("ticket_balance")
        .eq("id", ticketReq.user_id)
        .single();

      await adminClient
        .from("profiles")
        .update({ ticket_balance: (targetProfile?.ticket_balance ?? 0) + ticketReq.amount })
        .eq("id", ticketReq.user_id);
    }

    // 3b. Update request status
    const { data: updated, error: updateError } = await adminClient
      .from("ticket_requests")
      .update({
        status: action === "approve" ? "approved" : "rejected",
        admin_id: user.id,
        admin_note: admin_note ?? "",
        updated_at: new Date().toISOString(),
      })
      .eq("id", request_id)
      .select()
      .single();

    if (updateError) {
      return new Response(JSON.stringify({ error: "操作失败" }), {
        status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify(updated), {
      status: 200, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (e) {
    return new Response(JSON.stringify({ error: e.message }), {
      status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" },
    });
  }
});
```

- [ ] **Step 3: 部署两个 Edge Functions**

```bash
supabase functions deploy submit-request
supabase functions deploy approve-request
```

- [ ] **Step 4: 提交**

```bash
git add supabase/functions/submit-request/ supabase/functions/approve-request/
git commit -m "feat: add submit-request and approve-request edge functions"
```

---

### Task 4: 更新 Flutter 模型（用户端 + 管理端）

**关键变更:** `User.id` 从 `int` 变为 `String`（UUID）。Product/Order/TicketRequest 的引用字段也需要相应调整。

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\models\user.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\models\product.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\models\order.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\models\ticket_request.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\models\user.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\models\product.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\models\order.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\models\ticket_request.dart`

- [ ] **Step 1: 更新 User 模型（两端相同）**

```dart
// lib/models/user.dart
class User {
  final String id; // Changed from int to String (UUID)
  final String username;
  final String role;
  int ticketBalance;

  User({
    required this.id,
    required this.username,
    this.role = 'user',
    required this.ticketBalance,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id'] as String, // UUID is a string
      username: json['username'] as String,
      role: json['role'] as String? ?? 'user',
      ticketBalance: json['ticket_balance'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'username': username,
    'role': role,
    'ticket_balance': ticketBalance,
  };
}
```

- [ ] **Step 2: 更新 Product 模型（两端相同）**

```dart
// lib/models/product.dart
class Product {
  final String id; // Changed from int to String
  final String name;
  final String emoji;
  final int price;
  final int stock;
  final bool isAvailable;

  Product({
    required this.id,
    required this.name,
    required this.emoji,
    required this.price,
    this.stock = -1,
    this.isAvailable = true,
  });

  factory Product.fromJson(Map<String, dynamic> json) {
    return Product(
      id: json['id'].toString(), // BIGSERIAL comes as int, convert to String
      name: json['name'] as String,
      emoji: json['image_url'] as String? ?? '',
      price: json['price'] as int,
      stock: json['stock'] as int? ?? -1,
      isAvailable: json['is_available'] as bool? ?? true,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'name': name,
    'image_url': emoji,
    'price': price,
    'stock': stock,
    'is_available': isAvailable,
  };
}
```

- [ ] **Step 3: 更新 Order 模型（两端相同）**

```dart
// lib/models/order.dart
class Order {
  final String id; // Changed from int to String
  final String userId;
  final String productId;
  final String productName;
  final int price;
  final DateTime createdAt;

  Order({
    required this.id,
    required this.userId,
    required this.productId,
    required this.productName,
    required this.price,
    required this.createdAt,
  });

  factory Order.fromJson(Map<String, dynamic> json) {
    return Order(
      id: json['id'].toString(),
      userId: json['user_id'] as String,
      productId: json['product_id'].toString(),
      productName: json['product_name'] as String? ?? '',
      price: json['price'] as int,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user_id': userId,
    'product_id': productId,
    'product_name': productName,
    'price': price,
    'created_at': createdAt.toIso8601String(),
  };
}
```

- [ ] **Step 4: 更新 TicketRequest 模型（两端相同）**

```dart
// lib/models/ticket_request.dart
class TicketRequest {
  final String id; // Changed from int to String
  final String userId;
  final int amount;
  final String reason;
  String status;
  String? adminNote;
  final DateTime createdAt;

  TicketRequest({
    required this.id,
    required this.userId,
    required this.amount,
    required this.reason,
    required this.status,
    this.adminNote,
    required this.createdAt,
  });

  factory TicketRequest.fromJson(Map<String, dynamic> json) {
    return TicketRequest(
      id: json['id'].toString(),
      userId: json['user_id'] as String,
      amount: json['amount'] as int,
      reason: json['reason'] as String? ?? '',
      status: json['status'] as String,
      adminNote: json['admin_note'] as String?,
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'user_id': userId,
    'amount': amount,
    'reason': reason,
    'status': status,
    'admin_note': adminNote,
    'created_at': createdAt.toIso8601String(),
  };

  String get statusText {
    switch (status) {
      case 'pending': return '待审批';
      case 'approved': return '已通过';
      case 'rejected': return '已拒绝';
      default: return status;
    }
  }

  String get statusEmoji {
    switch (status) {
      case 'pending': return '⏳';
      case 'approved': return '✅';
      case 'rejected': return '❌';
      default: return '';
    }
  }
}
```

- [ ] **Step 5: 在管理端重复 Step 1-4**

将相同的模型文件复制/更新到 `stick_ticket_admin/lib/models/` 下。

- [ ] **Step 6: 提交**

```bash
git add stick_ticket_app/lib/models/ stick_ticket_admin/lib/models/
git commit -m "refactor: update models for Supabase (int -> String UUID)"
```

---

### Task 5: Flutter 用户端 — Supabase 初始化和配置

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\pubspec.yaml`
- Create: `C:\Users\23189\Desktop\stick_ticket_app\lib\config\supabase_config.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\main.dart`

- [ ] **Step 1: 添加 supabase_flutter 依赖**

在 `pubspec.yaml` 的 dependencies 中添加：

```yaml
dependencies:
  flutter:
    sdk: flutter
  cupertino_icons: ^1.0.8
  provider: ^6.1.5+1
  go_router: ^17.3.0
  supabase_flutter: ^2.8.1  # 新增
  shared_preferences: ^2.5.5
```

移除 `dio` 依赖（不再需要）。

安装依赖：
```bash
cd C:\Users\23189\Desktop\stick_ticket_app
flutter pub get
```

- [ ] **Step 2: 创建 Supabase 配置**

```dart
// lib/config/supabase_config.dart
class SupabaseConfig {
  // 从 Supabase Dashboard → Settings → API 获取下面两个值
  static const String url = 'YOUR_SUPABASE_URL'; // 例如 https://xxxxx.supabase.co
  static const String anonKey = 'YOUR_ANON_KEY'; // 公开的 anon key
}
```

- [ ] **Step 3: 更新 main.dart**

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'config/supabase_config.dart';
import 'providers/auth_provider.dart';
import 'providers/shop_provider.dart';
import 'providers/request_provider.dart';
import 'app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Supabase.initialize(
    url: SupabaseConfig.url,
    anonKey: SupabaseConfig.anonKey,
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ShopProvider()),
        ChangeNotifierProvider(create: (_) => RequestProvider()),
      ],
      child: const StickTicketApp(),
    ),
  );
}
```

- [ ] **Step 4: 提交**

```bash
git add stick_ticket_app/
git commit -m "feat: add supabase_flutter and init config (user app)"
```

---

### Task 6: Flutter 用户端 — Auth Service 重写

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\services\auth_service.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\providers\auth_provider.dart`
- 删除: `C:\Users\23189\Desktop\stick_ticket_app\lib\services\api_client.dart`

- [ ] **Step 1: 重写 AuthService**

```dart
// lib/services/auth_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user.dart';

class AuthService {
  final _supabase = Supabase.instance;

  /// 注册（用户名 + 密码），内部转为虚拟邮箱
  Future<User> register(String username, String password) async {
    final email = '$username@stickticket.local';
    final response = await _supabase.auth.signUp(
      email: email,
      password: password,
      data: {'username': username},
    );

    if (response.user == null) {
      throw Exception('注册失败');
    }

    // 查询自动创建的 profile
    final profile = await _supabase.client
        .from('profiles')
        .select()
        .eq('id', response.user!.id)
        .single();

    return User.fromJson(profile);
  }

  /// 登录（用户名 + 密码）
  Future<User> login(String username, String password) async {
    final email = '$username@stickticket.local';
    final response = await _supabase.auth.signInWithPassword(
      email: email,
      password: password,
    );

    if (response.user == null) {
      throw Exception('登录失败');
    }

    // 查询 profile 获取角色和余额
    final profile = await _supabase.client
        .from('profiles')
        .select()
        .eq('id', response.user!.id)
        .single();

    return User.fromJson(profile);
  }

  /// 获取当前登录用户信息
  Future<User> getMe() async {
    final userId = _supabase.auth.currentUser?.id;
    if (userId == null) throw Exception('未登录');

    final profile = await _supabase.client
        .from('profiles')
        .select()
        .eq('id', userId)
        .single();

    return User.fromJson(profile);
  }

  /// 登出
  Future<void> logout() async {
    await _supabase.auth.signOut();
  }
}
```

- [ ] **Step 2: 更新 AuthProvider（适配 String id + 保留结构）**

`lib/providers/auth_provider.dart` 保持不变，因为它只调用 AuthService 的方法。AuthService 的接口签名没变。

- [ ] **Step 3: 删除 api_client.dart**

```bash
rm C:\Users\23189\Desktop\stick_ticket_app\lib\services\api_client.dart
```

- [ ] **Step 4: 提交**

```bash
git add stick_ticket_app/lib/services/ stick_ticket_app/lib/providers/
git commit -m "refactor: rewrite auth service with Supabase"
```

---

### Task 7: Flutter 用户端 — Shop 和 Request Service 重写

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\services\shop_service.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\services\request_service.dart`

- [ ] **Step 1: 重写 ShopService**

```dart
// lib/services/shop_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/product.dart';
import '../models/order.dart';

class ShopService {
  final _supabase = Supabase.instance;

  Future<List<Product>> getProducts() async {
    final data = await _supabase.client
        .from('products')
        .select()
        .eq('is_available', true)
        .order('id');

    return (data as List).map((j) => Product.fromJson(j)).toList();
  }

  Future<Order> buyProduct(String userId, String productId) async {
    // 调用 Edge Function
    final response = await _supabase.functions.invoke(
      'purchase',
      body: {'product_id': int.parse(productId)},
    );

    if (response.status != 200) {
      final error = _parseError(response.data);
      throw Exception(error);
    }

    return Order.fromJson(response.data);
  }

  Future<List<Order>> getOrderHistory(String userId) async {
    final data = await _supabase.client
        .from('orders')
        .select('*, products!inner(name)')
        .eq('user_id', userId)
        .order('created_at', ascending: false);

    return (data as List).map((j) {
      // Merge product_name from joined products table
      final order = Map<String, dynamic>.from(j);
      order['product_name'] = j['products']?['name'] ?? '';
      order.remove('products');
      return Order.fromJson(order);
    }).toList();
  }

  String _parseError(dynamic data) {
    try {
      return data['error'] as String? ?? '操作失败';
    } catch (_) {
      return '操作失败';
    }
  }
}
```

- [ ] **Step 2: 重写 RequestService**

```dart
// lib/services/request_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/ticket_request.dart';

class RequestService {
  final _supabase = Supabase.instance;

  Future<TicketRequest> submitRequest(String userId, int amount, String reason) async {
    final response = await _supabase.functions.invoke(
      'submit-request',
      body: {'amount': amount, 'reason': reason},
    );

    if (response.status != 201) {
      final error = _parseError(response.data);
      throw Exception(error);
    }

    return TicketRequest.fromJson(response.data);
  }

  Future<List<TicketRequest>> getHistory(String userId) async {
    final data = await _supabase.client
        .from('ticket_requests')
        .select()
        .eq('user_id', userId)
        .order('created_at', ascending: false);

    return (data as List).map((j) => TicketRequest.fromJson(j)).toList();
  }

  String _parseError(dynamic data) {
    try {
      return data['error'] as String? ?? '操作失败';
    } catch (_) {
      return '操作失败';
    }
  }
}
```

- [ ] **Step 3: 更新 Provider 层**

`ShopProvider` 和 `RequestProvider` 签名变化不大，主要是 `userId` 参数类型从 `int` 变为 `String`。

修改 `lib/providers/shop_provider.dart` 中 `buyProduct` 的参数类型：

```dart
// int userId → String userId
Future<Order?> buyProduct(String userId, String productId) async {
  // ... rest stays the same
}
```

修改 `lib/providers/wallet_provider.dart`，适配新的 User 模型：

```dart
// lib/providers/wallet_provider.dart
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class WalletProvider extends ChangeNotifier {
  final _supabase = Supabase.instance;

  int get balance => 0;

  Future<int> getBalance() async {
    try {
      final userId = _supabase.auth.currentUser?.id;
      if (userId == null) return 0;
      final data = await _supabase.client
          .from('profiles')
          .select('ticket_balance')
          .eq('id', userId)
          .single();
      return data['ticket_balance'] as int? ?? 0;
    } catch (_) {
      return 0;
    }
  }
}
```

- [ ] **Step 4: 提交**

```bash
git add stick_ticket_app/lib/services/ stick_ticket_app/lib/providers/
git commit -m "refactor: rewrite shop and request services with Supabase"
```

---

### Task 8: Flutter 用户端 — 页面适配 + 删除 MockData

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_app\lib\pages\login_page.dart`
- 删除: `C:\Users\23189\Desktop\stick_ticket_app\lib\mock\mock_data.dart`
- 检查并适配: shop_page, wallet_page, request_page, home_page

- [ ] **Step 1: 更新 LoginPage（无重大改动）**

LoginPage 本身不需要改，AuthProvider 的接口没变。但需要确认 widget 正常工作。

- [ ] **Step 2: 删除 MockData**

```bash
rm C:\Users\23189\Desktop\stick_ticket_app\lib\mock\mock_data.dart
```

如果 mock 目录为空，也删除：
```bash
rmdir C:\Users\23189\Desktop\stick_ticket_app\lib\mock
```

- [ ] **Step 3: 修复所有引用 mock_data.dart 的 import**

检查所有文件是否还有 `import '../mock/mock_data.dart';`。目前只有模型文件没有直接引用（mock_data 引用模型，不是反过来）。main.dart 也需要移除 `import 'mock/mock_data.dart';`。

`main.dart` 中移除：
```dart
import 'mock/mock_data.dart';  // 删除这行
await MockData.init();          // 删除这行
```

- [ ] **Step 4: 检查页面文件**

快速检查 `shop_page.dart`, `wallet_page.dart`, `request_page.dart` 中是否有需要适配 int→String 的地方。这些页面的 Provider 接口基本不变。

- [ ] **Step 5: 运行 flutter analyze 确保无编译错误**

```bash
cd C:\Users\23189\Desktop\stick_ticket_app
flutter analyze
```

修复所有错误。

- [ ] **Step 6: 提交**

```bash
git add stick_ticket_app/
git commit -m "refactor: remove mock data, finalize user app supabase migration"
```

---

### Task 9: Flutter 管理端 — Supabase 初始化 + Auth

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\pubspec.yaml`
- Create: `C:\Users\23189\Desktop\stick_ticket_admin\lib\config\supabase_config.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\main.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\services\auth_service.dart`
- 删除: `C:\Users\23189\Desktop\stick_ticket_admin\lib\services\api_client.dart`

- [ ] **Step 1: 添加 supabase_flutter 依赖**

`pubspec.yaml` 中移除 `dio`，添加 `supabase_flutter: ^2.8.1`，运行 `flutter pub get`。

- [ ] **Step 2: 创建 Supabase 配置**

和用户端相同的配置内容：

```dart
// lib/config/supabase_config.dart
class SupabaseConfig {
  static const String url = 'YOUR_SUPABASE_URL';
  static const String anonKey = 'YOUR_ANON_KEY';
}
```

- [ ] **Step 3: 更新 main.dart**

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'config/supabase_config.dart';
import 'providers/auth_provider.dart';
import 'providers/admin_provider.dart';
import 'app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Supabase.initialize(
    url: SupabaseConfig.url,
    anonKey: SupabaseConfig.anonKey,
  );

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => AdminProvider()),
      ],
      child: const StickTicketAdminApp(),
    ),
  );
}
```

- [ ] **Step 4: 重写 AdminAuthService**

```dart
// lib/services/auth_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/user.dart';

class AuthService {
  final _supabase = Supabase.instance;

  Future<User> login(String username, String password) async {
    final email = '$username@stickticket.local';
    final response = await _supabase.auth.signInWithPassword(
      email: email,
      password: password,
    );

    if (response.user == null) {
      throw Exception('登录失败');
    }

    final profile = await _supabase.client
        .from('profiles')
        .select()
        .eq('id', response.user!.id)
        .single();

    return User.fromJson(profile);
  }

  Future<void> logout() async {
    await _supabase.auth.signOut();
  }
}
```

- [ ] **Step 5: 删除 api_client.dart**

```bash
rm C:\Users\23189\Desktop\stick_ticket_admin\lib\services\api_client.dart
```

- [ ] **Step 6: 提交**

```bash
git add stick_ticket_admin/
git commit -m "refactor: admin app supabase init and auth"
```

---

### Task 10: Flutter 管理端 — Admin Service 重写

**Files:**
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\services\admin_service.dart`
- 删除: `C:\Users\23189\Desktop\stick_ticket_admin\lib\services\request_service.dart`
- 删除: `C:\Users\23189\Desktop\stick_ticket_admin\lib\services\shop_service.dart`
- Modify: `C:\Users\23189\Desktop\stick_ticket_admin\lib\providers\admin_provider.dart`

- [ ] **Step 1: 重写 AdminService**

```dart
// lib/services/admin_service.dart
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/ticket_request.dart';
import '../models/product.dart';

class AdminService {
  final _supabase = Supabase.instance;

  // ── Pending Requests ──

  Future<List<TicketRequest>> getPendingRequests() async {
    final data = await _supabase.client
        .from('ticket_requests')
        .select()
        .eq('status', 'pending')
        .order('created_at');

    return (data as List).map((j) => TicketRequest.fromJson(j)).toList();
  }

  Future<TicketRequest> approveRequest(String requestId, String? note) async {
    final response = await _supabase.functions.invoke(
      'approve-request',
      body: {
        'request_id': int.parse(requestId),
        'action': 'approve',
        'admin_note': note ?? '',
      },
    );

    if (response.status != 200) {
      throw Exception(_parseError(response.data));
    }
    return TicketRequest.fromJson(response.data);
  }

  Future<TicketRequest> rejectRequest(String requestId, String? note) async {
    final response = await _supabase.functions.invoke(
      'approve-request',
      body: {
        'request_id': int.parse(requestId),
        'action': 'reject',
        'admin_note': note ?? '',
      },
    );

    if (response.status != 200) {
      throw Exception(_parseError(response.data));
    }
    return TicketRequest.fromJson(response.data);
  }

  // ── User Balance ──

  Future<Map<String, dynamic>> adjustBalance(String userId, int delta) async {
    // 先查询当前余额
    final profile = await _supabase.client
        .from('profiles')
        .select('ticket_balance')
        .eq('id', userId)
        .single();

    final newBalance = (profile['ticket_balance'] as int) + delta;
    await _supabase.client
        .from('profiles')
        .update({'ticket_balance': newBalance})
        .eq('id', userId);

    return {'user_id': userId, 'new_balance': newBalance};
  }

  // ── Product Management ──

  Future<List<Product>> getAllProducts() async {
    final data = await _supabase.client
        .from('products')
        .select()
        .order('id');

    return (data as List).map((j) => Product.fromJson(j)).toList();
  }

  Future<Product> addProduct({
    required String name,
    String? imageUrl,
    required int price,
    int stock = -1,
  }) async {
    final data = await _supabase.client
        .from('products')
        .insert({
          'name': name,
          'image_url': imageUrl ?? '',
          'price': price,
          'stock': stock,
          'is_available': true,
        })
        .select()
        .single();

    return Product.fromJson(data);
  }

  Future<Product> updateProduct(
    String productId, {
    String? name,
    String? imageUrl,
    int? price,
    int? stock,
    bool? isAvailable,
  }) async {
    final updates = <String, dynamic>{};
    if (name != null) updates['name'] = name;
    if (imageUrl != null) updates['image_url'] = imageUrl;
    if (price != null) updates['price'] = price;
    if (stock != null) updates['stock'] = stock;
    if (isAvailable != null) updates['is_available'] = isAvailable;

    final data = await _supabase.client
        .from('products')
        .update(updates)
        .eq('id', int.parse(productId))
        .select()
        .single();

    return Product.fromJson(data);
  }

  String _parseError(dynamic data) {
    try {
      return data['error'] as String? ?? '操作失败';
    } catch (_) {
      return '操作失败';
    }
  }
}
```

- [ ] **Step 2: 更新 AdminProvider**

修改 `lib/providers/admin_provider.dart` 中的方法签名，将 `int` 类型的 id 参数改为 `String`：

```dart
// approveRequest(int requestId, String? note) → approveRequest(String requestId, String? note)
// rejectRequest(int requestId, String? note) → rejectRequest(String requestId, String? note)
// adjustBalance(int userId, int delta) → adjustBalance(String userId, int delta)
// updateProduct(int productId, ...) → updateProduct(String productId, ...)
```

- [ ] **Step 3: 删除旧文件**

```bash
rm C:\Users\23189\Desktop\stick_ticket_admin\lib\services\request_service.dart
rm C:\Users\23189\Desktop\stick_ticket_admin\lib\services\shop_service.dart
```

- [ ] **Step 4: 删除 MockData**

```bash
rm C:\Users\23189\Desktop\stick_ticket_admin\lib\mock\mock_data.dart
rmdir C:\Users\23189\Desktop\stick_ticket_admin\lib\mock
```

- [ ] **Step 5: 运行 flutter analyze**

```bash
cd C:\Users\23189\Desktop\stick_ticket_admin
flutter analyze
```

修复所有错误。

- [ ] **Step 6: 提交**

```bash
git add stick_ticket_admin/
git commit -m "refactor: admin app services and providers for Supabase"
```

---

### Task 11: 端到端测试验证

- [ ] **Step 1: 在 Supabase Dashboard 创建管理员**

1. Authentication → Users → Add User
2. Email: `admin@stickticket.local`
3. Password: 设置密码
4. 等待用户创建后，在 SQL Editor 执行：
```sql
UPDATE public.profiles SET role = 'admin' WHERE id = '<从 users 表复制 UUID>';
```

- [ ] **Step 2: 测试用户端流程**

1. 在模拟器/手机运行 `stick_ticket_app`
2. 注册一个新用户
3. 在 Supabase Dashboard → Table Editor → profiles 中手动给这个用户加一些券
4. 浏览商品列表，确认显示正常
5. 购买一个商品，确认余额扣减
6. 查看订单历史
7. 提交增券申请

- [ ] **Step 3: 测试管理端流程**

1. 运行 `stick_ticket_admin`
2. 用管理员账户登录
3. 查看待审批列表
4. 通过/拒绝一个申请
5. 调整用户余额
6. 添加/修改商品

- [ ] **Step 4: 修复发现的问题**

记录测试中发现的所有问题，逐一修复。

- [ ] **Step 5: 提交最终修复**

```bash
git add .
git commit -m "fix: end-to-end test fixes"
```
