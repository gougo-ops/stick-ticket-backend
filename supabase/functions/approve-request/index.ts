// approve-request Edge Function — 管理员审批增券申请
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
