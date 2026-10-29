import React from "react";
import { AbsoluteFill, Audio, OffthreadVideo, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { ProgressBar, SceneCutFlash, useScenePunch } from "./MotionFx";
import { Subtitles } from "./Subtitles";
import { TitleOverlay } from "./TitleOverlay";
import type { ShortsProps } from "./types";

/** Paths in the props are relative to the project folder (Remotion's public dir); URLs pass through. */
const asset = (src?: string | null): string | undefined => {
  if (!src) return undefined;
  if (/^(https?:|data:)/.test(src)) return src;
  return staticFile(src.replace(/^[./\\]+/, ""));
};

// Layers, back to front: scene video (with a punch-in on cuts), narration + BGM, cut flash and
// progress bar, subtitles, then the 0–2 s opening title.
export const ShortsComposition: React.FC<ShortsProps> = ({ videoSrc, audioSrc, bgmSrc, bgmVolume = 0.15, subtitles, title, sceneStarts = [] }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const punch = useScenePunch(sceneStarts, frame, fps);
  const video = asset(videoSrc);
  const narration = asset(audioSrc);
  const music = asset(bgmSrc);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {video ? <OffthreadVideo src={video} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${punch})` }} /> : null}
      {narration ? <Audio src={narration} volume={1} /> : null}
      {music ? <Audio loop src={music} volume={bgmVolume} /> : null}
      <SceneCutFlash sceneStarts={sceneStarts} />
      <ProgressBar />
      <Subtitles subtitles={subtitles} />
      <TitleOverlay title={title ?? undefined} />
    </AbsoluteFill>
  );
};
