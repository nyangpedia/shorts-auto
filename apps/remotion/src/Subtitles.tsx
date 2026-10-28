import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Outlined, SHORTS_FONT } from "./Outlined";
import type { SubtitleItem } from "./types";

// Numbers (+ a trailing unit) pop in yellow: "초당 900도" -> "900도" highlighted.
const NUMBER_RE = /(\d[\d,.]*\s?(?:%|퍼센트|도|초|분|시간|일|년|배|개|명|원|만|억|조|km|kg|m|g)?)/g;

const highlightNumbers = (text: string): React.ReactNode[] =>
  text.split(NUMBER_RE).map((part, i) =>
    i % 2 === 1 ? (
      <span key={i} style={{ color: "#ffd400" }}>
        {part}
      </span>
    ) : (
      part
    )
  );

interface SubtitlesProps {
  subtitles: SubtitleItem[];
}

export const Subtitles: React.FC<SubtitlesProps> = ({ subtitles }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  const currentSub = subtitles.find((s) => currentTime >= s.start && currentTime <= s.end);
  if (!currentSub || !currentSub.text.trim()) {
    return null;
  }

  // Pop from 85% so a line never starts invisible.
  const relativeFrame = Math.max(0, frame - Math.round(currentSub.start * fps));
  const scale = 0.85 + 0.15 * spring({ frame: relativeFrame, fps, config: { damping: 14, stiffness: 220, mass: 0.8 } });
  const opacity = interpolate(relativeFrame, [0, 3], [0, 1], { extrapolateRight: "clamp" });
  const fontSize = currentSub.text.length > 18 ? 74 : currentSub.text.length > 12 ? 84 : 92;

  // Shorts style: no box, heavy white type with a thick black outline, sitting above the YouTube
  // caption/button overlay (bottom ~25%) and clear of the right-side action buttons.
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 520,
        display: "flex",
        justifyContent: "center",
        padding: "0 110px",
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      <Outlined
        outline={7}
        style={{
          transform: `scale(${scale})`,
          opacity,
          maxWidth: 860,
          textAlign: "center",
          fontFamily: SHORTS_FONT,
          fontSize,
          fontWeight: 900,
          lineHeight: 1.2,
          letterSpacing: "-2px",
          color: "#ffffff",
          wordBreak: "keep-all",
          textWrap: "balance", // two even lines instead of a long line + a stub
        }}
      >
        {highlightNumbers(currentSub.text)}
      </Outlined>
    </div>
  );
};
