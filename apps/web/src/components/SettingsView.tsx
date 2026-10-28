import { ChangeEvent, useEffect, useState } from "react";

import {
  disconnectYouTube,
  fetchKeyStatus,
  fetchYouTubeAuthUrl,
  fetchYouTubeStatus,
  saveClientSecret,
  saveKeys,
  type YouTubeStatus
} from "../api";

const KEYS: readonly { env: string; label: string; required: boolean; help: string; url: string }[] = [
  { env: "GEMINI_API_KEY", label: "Gemini API 키", required: true, help: "대본·분석·음성(TTS). 무료", url: "https://aistudio.google.com/apikey" },
  { env: "YOUTUBE_API_KEY", label: "YouTube Data API 키", required: true, help: "레퍼런스 검색. 무료 (하루 10,000포인트)", url: "https://console.cloud.google.com/apis/library/youtube.googleapis.com" },
  { env: "CLOUDFLARE_ACCOUNT_ID", label: "Cloudflare 계정 ID", required: true, help: "씬 이미지 생성. 무료 (하루 약 200장)", url: "https://dash.cloudflare.com/?to=/:account/ai/workers-ai" },
  { env: "CLOUDFLARE_API_TOKEN", label: "Cloudflare API 토큰", required: true, help: "Workers AI 권한으로 만든 토큰", url: "https://dash.cloudflare.com/profile/api-tokens" },
  { env: "OPENAI_API_KEY", label: "OpenAI API 키 (선택)", required: false, help: "유료. 비워 두면 Gemini를 씁니다", url: "https://platform.openai.com/api-keys" }
];

const errorText = (reason: unknown, fallback: string) => (reason instanceof Error ? reason.message : fallback);

export function SettingsView({ onSaved }: { readonly onSaved: () => void }) {
  const [keys, setKeys] = useState<Readonly<Record<string, boolean>>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [yt, setYt] = useState<YouTubeStatus | null>(null);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const loadYt = () => void fetchYouTubeStatus().then(setYt).catch(() => setYt(null));
  useEffect(() => {
    void fetchKeyStatus().then((r) => setKeys(r.keys)).catch((reason) => setMessage({ ok: false, text: errorText(reason, "설정을 불러오지 못했습니다.") }));
    loadYt();
  }, []);

  async function save(values: Record<string, string>, done: string) {
    try {
      setKeys((await saveKeys(values)).keys);
      setDrafts({});
      setMessage({ ok: true, text: done });
      onSaved();
    } catch (reason) {
      setMessage({ ok: false, text: errorText(reason, "저장하지 못했습니다.") });
    }
  }

  async function uploadSecret(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    try {
      setYt(await saveClientSecret(await file.text()));
      setMessage({ ok: true, text: "OAuth 클라이언트 파일을 저장했습니다. 이제 구글 계정을 연결하세요." });
    } catch (reason) {
      setMessage({ ok: false, text: errorText(reason, "파일을 저장하지 못했습니다.") });
    }
  }

  async function connect() {
    try {
      window.open((await fetchYouTubeAuthUrl()).auth_url, "_blank");
      setMessage({ ok: true, text: "새 창에서 구글 로그인 후 허용하고, 돌아와서 '연결 확인'을 누르세요." });
    } catch (reason) {
      setMessage({ ok: false, text: errorText(reason, "연결을 시작하지 못했습니다.") });
    }
  }

  const missing = KEYS.filter((k) => k.required && !keys[k.env]).length;
  const pending = Object.entries(drafts).filter(([, v]) => v.trim());

  return (
    <div className="stack">
      <div className="section-head">
        <h2>설정</h2>
        <p>키는 이 PC의 .env 파일에만 저장되고, 화면에는 다시 표시되지 않습니다.</p>
      </div>
      {message ? <div className={`banner ${message.ok ? "ok" : "bad"}`} role={message.ok ? "status" : "alert"}>{message.ok ? "✅" : "⚠️"} {message.text}</div> : null}

      <div className="card">
        <div className="section-head">
          <h2>API 키</h2>
          <p>{missing === 0 ? "필수 키가 모두 들어 있습니다." : `필수 키 ${missing}개가 비어 있습니다.`}</p>
        </div>
        <div className="keys">
          {KEYS.map((k) => (
            <div className="key-row" key={k.env}>
              <div>
                <b>{k.label}</b> <span className={`chip ${keys[k.env] ? "ok" : k.required ? "warn" : ""}`}>{keys[k.env] ? "설정됨" : "없음"}</span>
                <small className="muted" style={{ display: "block" }}>{k.help} · <a href={k.url} rel="noreferrer" target="_blank">발급받기 ↗</a></small>
              </div>
              <input
                aria-label={k.label}
                autoComplete="off"
                className="input"
                onChange={(e) => setDrafts({ ...drafts, [k.env]: e.target.value })}
                placeholder={keys[k.env] ? "바꾸려면 새 값 입력" : "붙여넣기"}
                type="password"
                value={drafts[k.env] ?? ""}
              />
              {keys[k.env] ? (
                <button className="btn small" onClick={() => window.confirm(`${k.label}를 지울까요?`) && void save({ [k.env]: "" }, `${k.label}를 지웠습니다.`)} type="button">지우기</button>
              ) : <span />}
            </div>
          ))}
        </div>
        <div className="row">
          <button className="btn accent" disabled={pending.length === 0} onClick={() => void save(Object.fromEntries(pending), "저장했습니다. 바로 적용됩니다.")} type="button">
            저장 {pending.length > 0 ? `(${pending.length})` : ""}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="section-head">
          <h2>유튜브 계정</h2>
          <p>업로드와 내 영상 분석에 씁니다. 선택 기능이고, 안 쓰면 영상을 내려받아 직접 올리면 됩니다.</p>
        </div>
        <ol className="steps-guide">
          <li className={yt?.configured ? "done" : ""}>
            구글 클라우드에서 <b>OAuth 클라이언트 ID (데스크톱 앱)</b>를 만들고 JSON 파일을 받아 올립니다.{" "}
            <a href="https://console.cloud.google.com/apis/credentials" rel="noreferrer" target="_blank">사용자 인증 정보 ↗</a>
            <label className="btn small file-btn">
              {yt?.configured ? "다른 파일로 바꾸기" : "JSON 파일 올리기"}
              <input accept="application/json,.json" onChange={(e) => void uploadSecret(e)} type="file" />
            </label>
          </li>
          <li className={yt?.connected ? "done" : ""}>
            구글 계정으로 로그인해 권한을 허용합니다. (업로드 · 내 채널 통계 읽기)
            <span className="row" style={{ display: "inline-flex", marginLeft: 8 }}>
              {yt?.connected ? (
                <>
                  <span className="chip ok">연결됨</span>
                  <button className="btn small" onClick={() => window.confirm("유튜브 연결을 끊을까요?") && void disconnectYouTube().then(setYt)} type="button">연결 끊기</button>
                </>
              ) : (
                <>
                  <button className="btn small accent" disabled={!yt?.configured} onClick={() => void connect()} type="button">구글 계정 연결</button>
                  <button className="btn small" disabled={!yt?.configured} onClick={loadYt} type="button">연결 확인</button>
                </>
              )}
            </span>
          </li>
        </ol>
        <p className="muted small">
          OAuth 동의 화면이 &lsquo;테스트&rsquo; 상태면 로그인이 7일마다 풀립니다. 연결이 되면 &lsquo;프로덕션으로 게시&rsquo;로 바꾸세요. 이때 나오는 &lsquo;확인되지 않은 앱&rsquo; 경고는 본인 앱이라 정상입니다.
        </p>
      </div>
    </div>
  );
}
