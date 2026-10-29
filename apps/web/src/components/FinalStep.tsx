import { useEffect, useState } from "react";

import { makeThumbnail, prepareUploadFiles } from "../api";
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
  readonly scenePictures: readonly { readonly id: number; readonly url: string }[];
  readonly thumbnailUrl: string | null;
}

const CHECKS = [
  ["사실 확인", "대본의 숫자와 주장을 검색으로 확인했나요? (대본 단계의 AI 사실 확인 결과 참고)"],
  ["내 관점 한 줄", "AI 대본 그대로가 아니라 내 의견·경험이 들어갔나요? 유튜브는 템플릿 대량생산형 영상의 수익화를 제한합니다."],
  ["합성 콘텐츠 표시", "실사처럼 보이는 사람·장면이 있으면 업로드할 때 '변경되었거나 합성된 콘텐츠'를 체크하세요."],
  ["제목·설명·태그", "아래 추천을 그대로 쓰지 말고 영상에 맞게 고쳤나요?"]
] as const;

/** Shorts descriptions carry #Shorts; add it once if the draft didn't. */
const withShortsTag = (text: string) => (!text.trim() || /#shorts/i.test(text) ? text : `${text.trim()}\n\n#Shorts`);
/** Studio's tag box takes comma-separated tags without '#'. */
const studioTags = (raw: string) => raw.replace(/#/g, " ").split(/[\s,]+/).filter(Boolean).join(", ");

function readChecks(projectId: string): boolean[] {
  try {
    const raw = localStorage.getItem(`checklist:${projectId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function FinalStep(props: FinalStepProps) {
  const { projectId, finalVideoUrl, candidate, videoTitle, scenesReady, isBusy, busyText, onTitleChange, onRender, scenePictures } = props;
  const [checks, setChecks] = useState<boolean[]>(() => readChecks(projectId));
  const [title, setTitle] = useState(videoTitle);
  const [videoVersion, setVideoVersion] = useState(0);
  const [uploadTitle, setUploadTitle] = useState(candidate?.title_options?.[0] ?? videoTitle);
  const [description, setDescription] = useState(withShortsTag(candidate?.description ?? ""));
  const [tags, setTags] = useState(studioTags(candidate?.tags ?? ""));
  const [prepared, setPrepared] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [thumbScene, setThumbScene] = useState(1);
  const [thumbTitle, setThumbTitle] = useState(videoTitle);
  const [thumbUrl, setThumbUrl] = useState<string | null>(props.thumbnailUrl);
  const [thumbBusy, setThumbBusy] = useState(false);
  const [thumbError, setThumbError] = useState<string | null>(null);

  useEffect(() => { setThumbUrl(props.thumbnailUrl ? `${props.thumbnailUrl}?v=${Date.now()}` : null); setThumbError(null); }, [projectId, props.thumbnailUrl]);
  useEffect(() => setThumbTitle(videoTitle), [videoTitle]);

  async function thumbnail() {
    setThumbBusy(true);
    setThumbError(null);
    try {
      const made = await makeThumbnail(projectId, thumbScene, thumbTitle || videoTitle);
      setThumbUrl(`${made.thumbnail_url}?v=${Date.now()}`);
    } catch (reason) {
      setThumbError(reason instanceof Error ? reason.message : "썸네일을 만들지 못했습니다.");
    } finally {
      setThumbBusy(false);
    }
  }

  useEffect(() => {
    setUploadTitle(candidate?.title_options?.[0] ?? videoTitle);
    setDescription(withShortsTag(candidate?.description ?? ""));
    setTags(studioTags(candidate?.tags ?? ""));
    setPrepared(null);
    setUploadError(null);
  }, [projectId, candidate]);

  async function prepareFiles() {
    setUploadError(null);
    try {
      const made = await prepareUploadFiles(projectId, uploadTitle || videoTitle);
      setPrepared(made.files.join(", "));
    } catch (reason) {
      setUploadError(reason instanceof Error ? reason.message : "파일을 준비하지 못했습니다.");
    }
  }

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

  const copy = (value: string, what = value) => {
    void navigator.clipboard?.writeText(value);
    setCopied(what);
  };
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

        {scenePictures.length > 0 && (
          <div className="card">
            <div className="section-head"><h2>썸네일</h2><p>채널 화면·검색에 보이는 표지. 업로드할 때 같이 올라갑니다</p></div>
            {thumbError ? <div className="banner bad" role="alert">⚠️ {thumbError}</div> : null}
            <div className="thumb-picks" role="radiogroup" aria-label="썸네일에 쓸 장면">
              {scenePictures.map((pic) => (
                <button aria-checked={thumbScene === pic.id} className="thumb-pick" key={pic.id} onClick={() => setThumbScene(pic.id)} role="radio" type="button">
                  <img alt={`${pic.id}번 장면`} src={pic.url} />
                </button>
              ))}
            </div>
            <label className="field">썸네일 문구 (짧을수록 크게 들어갑니다)
              <input className="input" maxLength={100} onChange={(e) => setThumbTitle(e.target.value)} value={thumbTitle} />
            </label>
            <div className="row">
              <button className="btn" disabled={thumbBusy || !(thumbTitle || videoTitle)} onClick={() => void thumbnail()} type="button">
                {thumbBusy ? "만드는 중…" : thumbUrl ? "다시 만들기" : "썸네일 만들기"}
              </button>
              {thumbUrl ? <a className="btn" download={`${projectId}_thumbnail.jpg`} href={thumbUrl}>⬇ 내려받기</a> : null}
            </div>
            {thumbUrl ? <img alt="썸네일 미리보기" className="thumb-preview" src={thumbUrl} /> : null}
          </div>
        )}

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

        {finalVideoUrl ? (
          <div className="card">
            <div className="section-head"><h2>유튜브에 올리기</h2><p>유튜브 스튜디오에서 직접 올립니다 (영상당 1분 정도)</p></div>
            {uploadError ? <div className="banner bad" role="alert">⚠️ {uploadError}</div> : null}
            <ol className="upload-steps">
              <li>
                <button className="btn" onClick={() => void prepareFiles()} type="button">파일 준비 + 폴더 열기</button>
                <span className="hint">{prepared ? `준비됨: ${prepared}` : "영상과 썸네일을 제목 이름으로 복사합니다. 유튜브가 파일 이름을 제목으로 씁니다."}</span>
              </li>
              <li>
                <a className="btn" href="https://www.youtube.com/upload" rel="noreferrer" target="_blank">유튜브 업로드 페이지 열기 ↗</a>
                <span className="hint">영상 파일을 끌어다 놓으세요.</span>
              </li>
              <li>아래 칸을 하나씩 복사해 붙여 넣고, 썸네일을 올리세요. 실사처럼 보이는 장면이 있으면 "변경되었거나 합성된 콘텐츠"를 체크하세요.</li>
            </ol>
            {([
              ["제목", uploadTitle, setUploadTitle, 1],
              ["설명", description, setDescription, 4],
              ["태그", tags, setTags, 1]
            ] as const).map(([label, value, set, rows]) => (
              <label className="field" key={label}>
                <span>{label} <button className="btn small" onClick={(e) => { e.preventDefault(); copy(value, label); }} type="button">{copied === label ? "복사됨 ✓" : "복사"}</button>
                  {label === "제목" ? <span className="hint"> {value.length}/100</span> : null}</span>
                {rows > 1
                  ? <textarea className="input" onChange={(e) => set(e.target.value)} rows={rows} value={value} />
                  : <input className="input" maxLength={label === "제목" ? 100 : undefined} onChange={(e) => set(e.target.value)} value={value} />}
              </label>
            ))}
          </div>
        ) : null}

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
