import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { Outlined, SHORTS_FONT } from "./Outlined";

const SHOW_SECONDS = 2.0;
const FADE_FROM = 1.5;
const LINE_CHARS = 10; // aim for ~10 characters per line, at most 3 lines
const SAFE_WIDTH = 1000;
const ENDS_IN_NUMBER = /[\d만억조천백]$/; // "230만" stays on the same line as "개의"

/**
 * Break a title into up to three balanced lines on word boundaries (Korean never breaks inside a word,
 * and a number stays with the word after it). A "\n" typed in the title wins.
 */
export const splitTitle = (title: string): string[] => {
  if (title.includes("\n")) return title.split("\n").map((l) => l.trim()).filter(Boolean);
  const lineCount = Math.min(3, Math.max(1, Math.ceil(title.length / LINE_CHARS)));
  const goal = title.length / lineCount;
  const lines: string[] = [];
  let line = "";
  for (const word of title.split(/\s+/)) {
    const longer = line ? `${line} ${word}` : word;
    const roomForMore = lines.length < lineCount - 1;
    if (line && longer.length > goal && roomForMore && !ENDS_IN_NUMBER.test(line)) {
      lines.push(line);
      line = word;
    } else {
      line = longer;
    }
  }
  if (line) lines.push(line);
  return lines;
};

/** Opening title for the first two seconds: visible from frame 0, fades and shrinks slightly at the end. */
export const TitleOverlay: React.FC<{ title?: string }> = ({ title }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!title?.trim() || frame > SHOW_SECONDS * fps) return null;

  const fade: [number, number] = [FADE_FROM * fps, SHOW_SECONDS * fps];
  const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
  const opacity = interpolate(frame, fade, [1, 0], clamp);
  const scale = interpolate(frame, fade, [1, 0.94], clamp);
  const lines = splitTitle(title.trim());
  // Shrink until the longest line fits the safe width (a Hangul glyph is about 1em wide).
  const longest = Math.max(...lines.map((l) => l.length));
  const fontSize = Math.round(Math.min(136, Math.max(64, SAFE_WIDTH / (longest * 0.98))));

  return (
    // Upper third: below YouTube's top icons (~200px), clear of the subject in the middle of the frame.
    <div style={{ position: "absolute", inset: 0, display: "flex", justifyContent: "center", alignItems: "flex-start", padding: "300px 40px 0", pointerEvents: "none", zIndex: 60 }}>
      <div style={{ transform: `scale(${scale})`, opacity, width: "100%", maxWidth: SAFE_WIDTH, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, textAlign: "center" }}>
        {lines.map((line, i) => (
          <Outlined
            key={i}
            outline={9}
            style={{
              fontFamily: SHORTS_FONT,
              fontSize,
              fontWeight: 900,
              lineHeight: 1.15,
              letterSpacing: "-3px",
              whiteSpace: "nowrap",
              // the last line is the punchline: yellow (a one-line title stays white)
              color: lines.length > 1 && i === lines.length - 1 ? "#ffd400" : "#ffffff",
            }}
          >
            {line}
          </Outlined>
        ))}
      </div>
    </div>
  );
};
