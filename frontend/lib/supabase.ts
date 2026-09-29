"use client";

import { createClient, type SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

export function supabaseConfig() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";
  return { url, anonKey, configured: Boolean(url && anonKey) };
}

export function getSupabase(): SupabaseClient | null {
  const { url, anonKey, configured } = supabaseConfig();
  if (!configured) return null;
  if (!client) client = createClient(url, anonKey);
  return client;
}
