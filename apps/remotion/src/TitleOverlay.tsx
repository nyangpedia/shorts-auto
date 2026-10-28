import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Outlined, SHORTS_FONT } from "./Outlined";

interface TitleOverlayProps {
  title?: string;
}

const TARGET_LINE_CHARS = 10;

/**
 * Long titles wrap on word boundaries into up to 3 balanced lines (Korean never breaks mid-word).
 * An explicit "\n" in the title wins.
 */
export const splitTitle = (title: string): string[] => {
  if (title.includes("\n")) return title.split("\n").map((l) => l.trim()).filter(Boolean);
  const words = title.split(/\s+/);
  const lineCount = Math.min(3, Math.max(1, Math.ceil(title.length / TARGET_LINE_CHARS)));
  const target = title.length / lineCount;
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const next = current ? `${current} ${word}` : word;
    if (current && next.length > target && lines.length < lineCount - 1) {
      lines.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) lines.push(current);
  return lines;
};

export const TitleOverlay: React.FC<TitleOverlayProps> = ({ title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!title || !title.trim()) {
    return null;
  }

  // 0초부터 바로 100%로 보이고, 1.5~2.0초에 페이드아웃
  const endFrame = Math.round(2.0 * fps);
  if (frame > endFrame) {
    return null;
  }
  const fadeStartFrame = Math.round(1.5 * fps);
  const opacity = interpolate(frame, [fadeStartFrame, endFrame], [1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const scale = interpolate(frame, [fadeStartFrame, endFrame], [1, 0.94], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  // Shrink until the longest line fits the ~1000px safe width (a Korean glyph is about 1em wide).
  const lines = splitTitle(title.trim());
  const maxLineLength = Math.max(...lines.map((l) => l.length));
  const fontSize = Math.round(Math.min(136, Math.max(64, 1000 / (maxLineLength * 0.98))));

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        padding: "0 40px 200px 40px", // 중앙보다 조금 위
        pointerEvents: "none",
        zIndex: 60, // 자막(50)보다 위
      }}
    >
      <div
        style={{
          transform: `scale(${scale})`,
          opacity,
          width: "100%",
          maxWidth: 1000,
          textAlign: "center",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: 8,
        }}
      >
        {lines.map((line, idx) => (
          <Outlined
            key={idx}
            outline={9}
            style={{
              fontFamily: SHORTS_FONT,
              fontSize,
              fontWeight: 900,
              lineHeight: 1.15,
              // 마지막 줄을 노란색으로 강조 (한 줄이면 흰색)
              color: lines.length > 1 && idx === lines.length - 1 ? "#ffd400" : "#ffffff",
              letterSpacing: "-3px",
              whiteSpace: "nowrap",
            }}
          >
            {line}
          </Outlined>
        ))}
      </div>
    </div>
  );
};
