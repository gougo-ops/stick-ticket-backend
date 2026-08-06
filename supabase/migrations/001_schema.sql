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

-- ticket_requests
ALTER TABLE public.ticket_requests ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own requests" ON public.ticket_requests
  FOR SELECT USING (auth.uid() = user_id
    OR (SELECT role FROM public.profiles WHERE id = auth.uid()) = 'admin');

-- 7. 索引
CREATE INDEX idx_orders_user_id ON public.orders(user_id);
CREATE INDEX idx_orders_created_at ON public.orders(created_at DESC);
CREATE INDEX idx_ticket_requests_user_id ON public.ticket_requests(user_id);
CREATE INDEX idx_ticket_requests_status ON public.ticket_requests(status);
CREATE INDEX idx_ticket_requests_created_at ON public.ticket_requests(created_at DESC);
CREATE INDEX idx_products_is_available ON public.products(is_available);
