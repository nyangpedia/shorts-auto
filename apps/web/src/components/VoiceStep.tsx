import { useEffect, useState } from "react";

import { VISUAL_STYLES } from "../models";
import type { ConceptKit } from "../types";

interface VoiceStepProps {
  readonly audioUrl: string | null;
  readonly durationSeconds: number | null;
  readonly conceptKit: ConceptKit | null;
  readonly sceneCount: number;
  readonly isBusy: boolean;
  readonly busyText: string | null;
  readonly onGenerateVoice: () => void;
  readonly onBuildScenes: (style: string) => void;
}

export function VoiceStep({ audioUrl, durationSeconds, conceptKit, sceneCount, isBusy, busyText, onGenerateVoice, onBuildScenes }: VoiceStepProps) {
  const [style, setStyle] = useState(conceptKit?.style_id ?? "webtoon");
  const [audioVersion, setAudioVersion] = useState(0);

  useEffect(() => {
    if (conceptKit?.style_id) setStyle(conceptKit.style_id);
  }, [conceptKit?.style_id]);
  useEffect(() => setAudioVersion(Date.now()), [durationSeconds]);

  return (
    <div className="stack">
      {busyText ? <div className="banner busy">⏳ {busyText}</div> : null}
      <div className="grid2">
        <div className="card">
          <div className="section-head"><h2>내레이션</h2><p>확정한 대본을 1.2배속으로 읽습니다</p></div>
          {audioUrl ? (
            <>
              <audio className="audio" controls src={`${audioUrl}?v=${audioVersion}`} />
              <p className="muted small">길이 {durationSeconds ? `${durationSeconds.toFixed(1)}초` : "-"} · 목소리는 .env의 GEMINI_TTS_VOICE로 바꿀 수 있습니다</p>
            </>
          ) : (
            <p className="muted">아직 음성이 없습니다.</p>
          )}
          <div className="row">
            <button className={audioUrl ? "btn" : "btn accent"} disabled={isBusy} onClick={onGenerateVoice} type="button">
              {audioUrl ? "음성 다시 만들기" : "음성 만들기"}
            </button>
          </div>
        </div>

        <div className="card">
          <div className="section-head"><h2>화풍</h2><p>모든 씬에 같은 화풍과 주인공이 적용됩니다</p></div>
          <div className="chips">
            {VISUAL_STYLES.map((s) => (
              <button aria-pressed={style === s.id} key={s.id} onClick={() => setStyle(s.id)} type="button">{s.label}</button>
            ))}
          </div>
          {conceptKit ? <p className="muted small" style={{ marginTop: 12 }}>현재 씬 {sceneCount}개 · {conceptKit.visual_style}</p> : null}
          <div className="row">
            <button className={conceptKit ? "btn" : "btn accent"} disabled={isBusy || !audioUrl} onClick={() => onBuildScenes(style)} title={!audioUrl ? "음성을 먼저 만들어주세요" : undefined} type="button">
              {conceptKit ? "이 화풍으로 씬 다시 구성" : "씬 구성하기"}
            </button>
          </div>
          {conceptKit ? <p className="muted small">다시 구성하면 씬 이미지와 영상도 새로 만들어야 합니다.</p> : null}
        </div>
      </div>
    </div>
  );
}
