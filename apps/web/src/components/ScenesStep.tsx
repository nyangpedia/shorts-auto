import { useEffect, useState } from "react";

import { IMAGE_MODELS, VIDEO_MODELS, modelLabel } from "../models";
import type { VideoSceneItem } from "../types";

interface ScenesStepProps {
  readonly scenes: readonly VideoSceneItem[];
  readonly isBusy: boolean;
  readonly onGenerateImage: (sceneId: number, model: string) => Promise<void>;
  readonly onGenerateAllImages: (model: string) => Promise<void>;
  readonly onGenerateVideo: (sceneId: number, model: string) => Promise<void>;
  readonly onRegenerate: (sceneId: number, feedback: string, target: "image" | "video", model: string) => Promise<void>;
  readonly onUpdatePrompts: (sceneId: number, imagePrompt: string, videoPrompt: string) => Promise<void>;
}

export function ScenesStep(props: ScenesStepProps) {
  const { scenes, isBusy } = props;
  const [imageModel, setImageModel] = useState("cloudflare");
  const [videoModel, setVideoModel] = useState("kenburns");
  const [selectedId, setSelectedId] = useState<number | null>(scenes[0]?.scene_id ?? null);
  const [working, setWorking] = useState<Record<number, boolean>>({});
  const [batch, setBatch] = useState<string | null>(null);
  const [feedback, setFeedback] = useState("");
  const [imagePrompt, setImagePrompt] = useState("");
  const [videoPrompt, setVideoPrompt] = useState("");
  const [version, setVersion] = useState(0);

  const selected = scenes.find((s) => s.scene_id === selectedId) ?? scenes[0] ?? null;
  useEffect(() => {
    setImagePrompt(selected?.start_image_prompt ?? "");
    setVideoPrompt(selected?.video_prompt ?? "");
    setFeedback("");
  }, [selected?.scene_id, selected?.start_image_prompt, selected?.video_prompt]);

  if (scenes.length === 0) {
    return <p className="empty">음성·화풍 단계에서 씬을 먼저 구성해주세요.</p>;
  }

  const withImage = scenes.filter((s) => s.start_image_url).length;
  const withVideo = scenes.filter((s) => s.generated_video_url).length;
  const busy = isBusy || batch !== null;
  const media = (url: string | null) => (url ? `${url}${url.includes("?") ? "&" : "?"}v=${version}` : undefined);

  async function run(sceneId: number, task: () => Promise<void>) {
    setWorking((w) => ({ ...w, [sceneId]: true }));
    try {
      await task();
    } finally {
      setWorking((w) => ({ ...w, [sceneId]: false }));
      setVersion(Date.now());
    }
  }

  async function allImages() {
    setBatch(`이미지 ${scenes.length}장 만드는 중…`);
    try {
      await props.onGenerateAllImages(imageModel);
    } finally {
      setBatch(null);
      setVersion(Date.now());
    }
  }

  async function missingVideos() {
    const todo = scenes.filter((s) => s.start_image_url && !s.generated_video_url);
    for (const [i, scene] of todo.entries()) {
      setBatch(`영상 만드는 중… ${i + 1}/${todo.length}`);
      await run(scene.scene_id, () => props.onGenerateVideo(scene.scene_id, videoModel));
    }
    setBatch(null);
  }

  const dot = (s: VideoSceneItem) => (working[s.scene_id] ? "busy" : s.generated_video_url ? "video" : s.start_image_url ? "image" : "");

  return (
    <div>
      <div className="toolbar">
        <label className="field">이미지
          <select className="select" onChange={(e) => setImageModel(e.target.value)} value={imageModel}>
            {IMAGE_MODELS.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
          </select>
        </label>
        <label className="field">움직임
          <select className="select" onChange={(e) => setVideoModel(e.target.value)} value={videoModel}>
            {VIDEO_MODELS.map((m) => <option key={m.id} value={m.id}>{modelLabel(m)}</option>)}
          </select>
        </label>
        <span className="spacer" />
        <span className={`chip ${withImage === scenes.length ? "ok" : "warn"}`}>이미지 {withImage}/{scenes.length}</span>
        <span className={`chip ${withVideo === scenes.length ? "ok" : "warn"}`}>영상 {withVideo}/{scenes.length}</span>
        <button className="btn" disabled={busy} onClick={allImages} type="button">{withImage ? "이미지 전부 다시" : "이미지 전부 만들기"}</button>
        <button className="btn primary" disabled={busy || withImage === withVideo} onClick={missingVideos} type="button">
          남은 영상 {Math.max(0, withImage - withVideo)}개 만들기
        </button>
      </div>
      {batch ? <div className="banner busy">⏳ {batch}</div> : null}
      {!IMAGE_MODELS.find((m) => m.id === imageModel)?.free || !VIDEO_MODELS.find((m) => m.id === videoModel)?.free ? (
        <div className="banner warn">유료 모델을 골랐습니다. Higgsfield/OpenAI 계정과 크레딧이 필요하고 비용이 발생합니다.</div>
      ) : null}

      <div className="board">
        <div className="scenes">
          {scenes.map((s) => (
            <button aria-label={`씬 ${s.scene_id}`} aria-pressed={selected?.scene_id === s.scene_id} className="scene" key={s.scene_id} onClick={() => setSelectedId(s.scene_id)} type="button">
              <div className="scene-thumb">
                <span className="scene-no">{s.scene_id}</span>
                <span className={`scene-dot ${dot(s)}`} title={s.generated_video_url ? "영상 완료" : s.start_image_url ? "이미지만 있음" : "비어 있음"} />
                {s.start_image_url ? <img alt="" loading="lazy" src={media(s.start_image_url)} /> : "이미지 없음"}
              </div>
              <p>{s.narration}</p>
            </button>
          ))}
        </div>

        {selected && (
          <aside className="card drawer">
            <div className="drawer-preview">
              {selected.generated_video_url ? (
                <video autoPlay className="media" loop muted src={media(selected.generated_video_url)} />
              ) : selected.start_image_url ? (
                <img alt="" className="media" src={media(selected.start_image_url)} />
              ) : (
                <div className="media" />
              )}
              <div>
                <h3>씬 {selected.scene_id}</h3>
                <p className="muted small" style={{ margin: "0 0 8px", lineHeight: 1.5 }}>{selected.narration}</p>
                <span className={`chip ${selected.start_image_url ? "ok" : ""}`}>이미지 {selected.start_image_url ? "✓" : "없음"}</span>{" "}
                <span className={`chip ${selected.generated_video_url ? "ok" : ""}`}>영상 {selected.generated_video_url ? "✓" : "없음"}</span>
              </div>
            </div>

            <div className="label">이렇게 바꿔주세요</div>
            <textarea aria-label="씬 수정 요청" className="textarea" onChange={(e) => setFeedback(e.target.value)} placeholder="예: 인물을 더 크게, 배경은 밤으로" rows={3} value={feedback} />
            <div className="row">
              {feedback.trim() ? (
                <button className="btn primary" disabled={busy || working[selected.scene_id]} onClick={() => run(selected.scene_id, () => props.onRegenerate(selected.scene_id, feedback, "image", imageModel))} type="button">요청대로 이미지 다시</button>
              ) : (
                <button className="btn primary" disabled={busy || working[selected.scene_id]} onClick={() => run(selected.scene_id, () => props.onGenerateImage(selected.scene_id, imageModel))} type="button">{selected.start_image_url ? "이미지 다시" : "이미지 만들기"}</button>
              )}
              <button className="btn" disabled={busy || working[selected.scene_id] || !selected.start_image_url} onClick={() => run(selected.scene_id, () => props.onGenerateVideo(selected.scene_id, videoModel))} type="button">영상 {selected.generated_video_url ? "다시" : "만들기"}</button>
            </div>

            <details className="more">
              <summary>고급: 프롬프트 직접 수정</summary>
              <label className="field" style={{ marginTop: 8 }}>이미지 프롬프트
                <textarea className="textarea" onChange={(e) => setImagePrompt(e.target.value)} rows={5} value={imagePrompt} />
              </label>
              <label className="field" style={{ marginTop: 8 }}>영상 프롬프트 (유료 영상 모델용)
                <textarea className="textarea" onChange={(e) => setVideoPrompt(e.target.value)} rows={3} value={videoPrompt} />
              </label>
              <div className="row">
                <button className="btn small" disabled={busy || (imagePrompt === selected.start_image_prompt && videoPrompt === selected.video_prompt)} onClick={() => props.onUpdatePrompts(selected.scene_id, imagePrompt, videoPrompt)} type="button">프롬프트 저장</button>
              </div>
            </details>
          </aside>
        )}
      </div>
    </div>
  );
}
