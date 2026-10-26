import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";

const PUNCH_FRAMES = 6;
const FLASH_FRAMES = 4;

const framesSinceCut = (sceneStarts: number[], frame: number, fps: number): number | null => {
  let best: number | null = null;
  for (const t of sceneStarts) {
    const since = frame - Math.round(t * fps);
    if (since >= 0 && (best === null || since < best)) best = since;
  }
  return best;
};

// Quick zoom "punch" on every scene cut: 1.06 -> 1.0 over PUNCH_FRAMES.
export const useScenePunch = (sceneStarts: number[], frame: number, fps: number): number => {
  const since = framesSinceCut(sceneStarts, frame, fps);
  if (since === null || since > PUNCH_FRAMES) return 1;
  return interpolate(since, [0, PUNCH_FRAMES], [1.06, 1], { extrapolateRight: "clamp" });
};

export const SceneCutFlash: React.FC<{ sceneStarts: number[] }> = ({ sceneStarts }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const since = framesSinceCut(sceneStarts, frame, fps);
  if (since === null || since > FLASH_FRAMES) return null;
  const opacity = interpolate(since, [0, FLASH_FRAMES], [0.35, 0], { extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ backgroundColor: "#ffffff", opacity, pointerEvents: "none", zIndex: 40 }} />;
};

export const ProgressBar: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const pct = Math.min(100, (frame / Math.max(1, durationInFrames - 1)) * 100);
  return (
    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 12, background: "rgba(0,0,0,0.35)", zIndex: 60 }}>
      <div style={{ width: `${pct}%`, height: "100%", background: "#ffd400" }} />
    </div>
  );
};
