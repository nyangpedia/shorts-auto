import { useEffect, useState, type CSSProperties, type FormEvent, type ReactNode } from "react";

import "../login.css";
import { supabase } from "../supabase";

const CAPTION = ["아이디어", "한 줄이", "쇼츠", "한 편으로"];
const SPARK_X = [8, 18, 30, 42, 50, 58, 66, 74, 84];

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

  async function google() {
    if (!supabase || busy) return;
    setMessage("");
    const { error } = await supabase.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });
    if (error) setMessage("구글 로그인을 시작하지 못했어요. 잠시 뒤에 다시 해 주세요.");
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
    <main className="lg">
      <section className="lg-side">
        <div className="lg-brand">
          <img alt="" src="/logo.svg" />
          쇼츠공방
        </div>
        <h1 aria-label={CAPTION.join(" ")} className="lg-caption">
          {CAPTION.map((word, i) => (
            <span key={word}>
              <span aria-hidden="true" style={{ "--i": i } as CSSProperties}>{word}</span>
              {i === 1 ? <br /> : " "}
            </span>
          ))}
        </h1>
        <form className="lg-card" onSubmit={submit}>
          <button className="lg-btn google" onClick={() => void google()} type="button">
            <svg aria-hidden="true" height="18" viewBox="0 0 48 48" width="18">
              <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z" />
              <path fill="#4285F4" d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.6 5.9c4.4-4.1 7-10.1 7-17.6z" />
              <path fill="#FBBC05" d="M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z" />
              <path fill="#34A853" d="M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.6-5.9c-2.1 1.4-4.9 2.3-8.3 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z" />
            </svg>
            구글로 로그인
          </button>
          <div className="lg-or">또는 이메일로</div>
          <label>
            이메일
            <input autoComplete="email" onChange={(e) => setEmail(e.target.value)} required type="email" value={email} />
          </label>
          <label>
            비밀번호
            <input autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} required type="password" value={password} />
          </label>
          {message && <p className="lg-error" role="alert">{message}</p>}
          <button className="lg-btn go" disabled={busy} type="submit">{busy ? "확인 중…" : "로그인"}</button>
          <p className="lg-note">글모아에 가입한 계정(같은 구글·이메일)으로 로그인합니다.</p>
        </form>
      </section>

      <section aria-hidden="true" className="lg-stage">
        <div className="lg-phone a">
          <div className="lg-bar" style={{ "--p": "70%" } as CSSProperties} />
          <div className="lg-sun" />
          <p className="lg-sub">지구가 <b>멈추면</b><br />어떻게 될까?</p>
        </div>
        <div className="lg-phone b">
          <div className="lg-bar" style={{ "--p": "35%" } as CSSProperties} />
          <div className="lg-sun" />
          <p className="lg-sub">대본부터 <b>자막</b>까지<br />한 번에</p>
        </div>
        <div className="lg-phone c">
          <div className="lg-bar" style={{ "--p": "90%" } as CSSProperties} />
          <div className="lg-sun" />
          <p className="lg-sub">이게 <b>진짜</b>라고?</p>
        </div>
        <div className="lg-sparks">
          {SPARK_X.map((x, i) => (
            <i
              key={x}
              style={{ "--x": `${x}%`, "--dx": `${(i % 2 ? 1 : -1) * (20 + i * 6)}px`, "--dy": `${-90 - (i % 4) * 40}px`, "--t": `${0.2 + (i % 5) * 0.25}s` } as CSSProperties}
            />
          ))}
        </div>
      </section>
    </main>
  );
}
