import { useEffect, useState, type FormEvent, type ReactNode } from "react";

import { supabase } from "../supabase";

// ponytail: screen-only gate for a local app (edit the code and it opens). Server-side token check + usage limits come later.
export function LoginGate({ children }: { readonly children: ReactNode }) {
  const [signedIn, setSignedIn] = useState<boolean | null>(supabase ? null : true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!supabase) return;
    void supabase.auth.getSession().then(({ data }) => setSignedIn(Boolean(data.session)));
    const { data } = supabase.auth.onAuthStateChange((_event, session) => setSignedIn(Boolean(session)));
    return () => data.subscription.unsubscribe();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase || busy) return;
    setBusy(true);
    setMessage("");
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password });
    setBusy(false);
    // One sentence for every failure so it doesn't reveal whether the email is registered.
    if (error) setMessage(error.status === 429 ? "요청이 너무 많아요. 잠시 뒤에 다시 해 주세요." : "이메일 또는 비밀번호가 올바르지 않습니다.");
  }

  if (signedIn === null) return null;
  if (signedIn) {
    return (
      <>
        {children}
        {supabase && (
          <button
            className="secondary-button"
            onClick={() => void supabase?.auth.signOut()}
            style={{ position: "fixed", right: 12, bottom: 12, width: "auto", padding: "4px 12px", fontSize: 12, zIndex: 50 }}
            type="button"
          >
            로그아웃
          </button>
        )}
      </>
    );
  }

  return (
    <main style={{ display: "grid", placeItems: "center", minHeight: "100vh" }}>
      <form className="panel" onSubmit={submit} style={{ width: 340, display: "grid", gap: 12 }}>
        <h1 style={{ margin: 0, fontSize: 22 }}>쇼츠공방 로그인</h1>
        <label>
          <span>이메일</span>
          <input autoComplete="email" onChange={(e) => setEmail(e.target.value)} required type="email" value={email} />
        </label>
        <label>
          <span>비밀번호</span>
          <input autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} required type="password" value={password} />
        </label>
        {message && <p role="alert" style={{ margin: 0, color: "#dc2626", fontSize: 13 }}>{message}</p>}
        <button className="primary-button" disabled={busy} type="submit">{busy ? "확인 중…" : "로그인"}</button>
        <p style={{ margin: 0, fontSize: 12, color: "#64748b" }}>글모아에 가입한 계정으로 로그인합니다.</p>
      </form>
    </main>
  );
}
