import { useEffect, useState } from "react";

import type { ScriptCandidate } from "../types";

interface FinalStepProps {
  readonly projectId: string;
  readonly finalVideoUrl: string | null;
  readonly candidate: ScriptCandidate | null;
  readonly videoTitle: string;
  readonly scenesReady: boolean;
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onTitleChange: (title: string) => void;
  readonly onRender: (title: string) => void;
}

const CHECKS = [
  ["사실 확인", "대본의 숫자와 주장을 검색으로 확인했나요? (대본 단계의 AI 사실 확인 결과 참고)"],
  ["내 관점 한 줄", "AI 대본 그대로가 아니라 내 의견·경험이 들어갔나요? 유튜브는 템플릿 대량생산형 영상의 수익화를 제한합니다."],
  ["합성 콘텐츠 표시", "실사처럼 보이는 사람·장면이 있으면 업로드할 때 '변경되었거나 합성된 콘텐츠'를 체크하세요."],
  ["제목·설명·태그", "아래 추천을 그대로 쓰지 말고 영상에 맞게 고쳤나요?"]
] as const;

function readChecks(projectId: string): boolean[] {
  try {
    const raw = localStorage.getItem(`checklist:${projectId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function FinalStep({ projectId, finalVideoUrl, candidate, videoTitle, scenesReady, isBusy, busyText, onTitleChange, onRender }: FinalStepProps) {
  const [checks, setChecks] = useState<boolean[]>(() => readChecks(projectId));
  const [title, setTitle] = useState(videoTitle);
  const [videoVersion, setVideoVersion] = useState(0);

  useEffect(() => setChecks(readChecks(projectId)), [projectId]);
  useEffect(() => setTitle(videoTitle), [videoTitle]);
  useEffect(() => setVideoVersion(Date.now()), [finalVideoUrl]);

  function toggle(i: number) {
    const next = CHECKS.map((_, j) => (j === i ? !checks[j] : Boolean(checks[j])));
    setChecks(next);
    try {
      localStorage.setItem(`checklist:${projectId}`, JSON.stringify(next));
    } catch {
      // per-browser convenience only
    }
  }

  const copy = (value: string) => void navigator.clipboard?.writeText(value);
  const metas = [
    ...(candidate?.title_options ?? []).map((t) => ["제목", t]),
    ...(candidate?.tags ? [["태그", candidate.tags]] : []),
    ...(candidate?.description ? [["설명", candidate.description]] : [])
  ];

  return (
    <div className="final">
      <div>
        {finalVideoUrl ? (
          <video controls src={`${finalVideoUrl}?v=${videoVersion}`} />
        ) : (
          <div className="video-empty">아직 렌더링하지 않았습니다.<br />오른쪽에서 렌더링하세요.</div>
        )}
        {finalVideoUrl ? (
          <div className="row"><a className="btn" download={`${projectId}.mp4`} href={finalVideoUrl}>⬇ 영상 내려받기</a></div>
        ) : null}
      </div>

      <div className="stack">
        {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}
        <div className="card">
          <div className="section-head"><h2>렌더링</h2><p>자막·BGM·모션그래픽을 입혀 9:16 영상으로 만듭니다 (약 5분)</p></div>
          <label className="field">첫 2초 화면 제목 (비우면 표시 안 함)
            <input className="input" onBlur={() => title !== videoTitle && onTitleChange(title)} onChange={(e) => setTitle(e.target.value)} value={title} />
          </label>
          <div className="row">
            <button className="btn accent" disabled={isBusy || !scenesReady} onClick={() => onRender(title)} title={!scenesReady ? "모든 씬에 이미지가 있어야 합니다" : undefined} type="button">
              {finalVideoUrl ? "다시 렌더링" : "렌더링 시작"}
            </button>
          </div>
        </div>

        <div className="card">
          <div className="section-head"><h2>업로드 전 확인</h2><p>{checks.filter(Boolean).length}/{CHECKS.length}</p></div>
          <ul className="check">
            {CHECKS.map(([label, help], i) => (
              <li key={label}>
                <label><input checked={Boolean(checks[i])} onChange={() => toggle(i)} type="checkbox" /><span><b>{label}</b> — {help}</span></label>
              </li>
            ))}
          </ul>
        </div>

        {metas.length > 0 && (
          <div className="card">
            <div className="section-head"><h2>제목·태그 추천</h2><p>눌러서 복사</p></div>
            <div className="meta-list">
              {metas.map(([kind, value], i) => (
                <div className="meta-item" key={i}>
                  <span><span className="chip">{kind}</span> {value}</span>
                  <button className="btn small" onClick={() => copy(value)} type="button">복사</button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
