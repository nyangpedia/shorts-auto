import React from "react";
import { Composition } from "remotion";
import { ShortsComposition } from "./ShortsComposition";
import type { ShortsProps } from "./types";

const FPS = 24;
const PREVIEW_PROPS: ShortsProps = {
  videoSrc: "",
  audioSrc: "",
  bgmSrc: null,
  bgmVolume: 0.15,
  subtitles: [],
  durationInFrames: FPS * 30,
  title: null,
  sceneStarts: [],
};

// 1080x1920 vertical Short; its length comes from the narration (durationInFrames in the props).
export const RemotionRoot: React.FC = () => (
  <Composition
    id="ShortsVideo"
    component={ShortsComposition as unknown as React.FC<Record<string, unknown>>}
    width={1080}
    height={1920}
    fps={FPS}
    durationInFrames={PREVIEW_PROPS.durationInFrames}
    defaultProps={PREVIEW_PROPS as unknown as Record<string, unknown>}
    calculateMetadata={async ({ props }) => ({
      durationInFrames: Math.max(FPS, Number((props as unknown as ShortsProps).durationInFrames) || FPS * 30),
      props,
    })}
  />
);
