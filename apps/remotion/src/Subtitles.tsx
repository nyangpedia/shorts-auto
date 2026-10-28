import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Outlined, SHORTS_FONT } from "./Outlined";
import type { SubtitleItem } from "./types";

const HIGHLIGHT = "#ffd400";

// Fallback for subtitles without word timings: numbers (+ a trailing unit) pop in yellow.
const NUMBER_RE = /(\d[\d,.]*\s?(?:%|퍼센트|도|초|분|시간|일|년|배|개|명|원|만|억|조|km|kg|m|g)?)/g;

const highlightNumbers = (text: string): React.ReactNode[] =>
  text.split(NUMBER_RE).map((part, i) =>
    i % 2 === 1 ? (
      <span key={i} style={{ color: HIGHLIGHT }}>
        {part}
      </span>
    ) : (
      part
    )
  );

interface SubtitlesProps {
  subtitles: SubtitleItem[];
}

// The line sits at ~68% of the 1920px height: below faces/subjects in the middle, above the YouTube
// caption/channel overlay (bottom ~25%), and narrow enough to stay clear of the right-side buttons.
const LINE_CENTER_FROM_BOTTOM = 620;
const MAX_WIDTH = 820;

// Approximate Pretendard Black advance widths (in em, after the -2px tracking): Hangul is nearly
// square, Latin/digits about half, spaces narrow.
const lineWidthEm = (text: string): number =>
  [...text].reduce((sum, ch) => sum + (/[가-힣]/.test(ch) ? 0.92 : ch === " " ? 0.26 : 0.6), 0);

export const Subtitles: React.FC<SubtitlesProps> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;

  const current = subtitles.find((s) => t >= s.start && t < s.end);
  if (!current || !current.text.trim()) {
    return null;
  }

  // Pop from 85% so a line never starts invisible.
  const relativeFrame = Math.max(0, frame - Math.round(current.start * fps));
  const scale = 0.85 + 0.15 * spring({ frame: relativeFrame, fps, config: { damping: 14, stiffness: 220, mass: 0.8 } });
  const opacity = interpolate(relativeFrame, [0, 3], [0, 1], { extrapolateRight: "clamp" });
  // Always one line: size the font so the line just fits instead of wrapping.
  const fontSize = Math.round(Math.min(104, MAX_WIDTH / lineWidthEm(current.text)));

  // The spoken word stays lit through a pause until the next word starts.
  const words = current.words;
  let active = -1;
  words?.forEach((w, i) => {
    if (t >= w.start) active = i;
  });

  const line = words
    ? words.map((w, i) => (
        <React.Fragment key={i}>
          {i > 0 ? " " : null}
          <span style={{ color: i === active ? HIGHLIGHT : "#ffffff" }}>{w.text}</span>
        </React.Fragment>
      ))
    : highlightNumbers(current.text);

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: LINE_CENTER_FROM_BOTTOM - fontSize * 0.6,
        display: "flex",
        justifyContent: "center",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <Outlined
        outline={7}
        style={{
          transform: `scale(${scale})`,
          opacity,
          maxWidth: MAX_WIDTH,
          textAlign: "center",
          whiteSpace: "nowrap",
          fontFamily: SHORTS_FONT,
          fontSize,
          fontWeight: 900,
          lineHeight: 1.2,
          letterSpacing: "-2px",
          color: "#ffffff",
        }}
      >
        {line}
      </Outlined>
    </div>
  );
};
