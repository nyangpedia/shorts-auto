import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const key = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;

// No values -> login is off and the app opens as before (tests, open-source use).
export const supabase = url && key ? createClient(url, key) : null;
