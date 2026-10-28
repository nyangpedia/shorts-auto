import React from "react";
import { continueRender, delayRender } from "remotion";
import pretendardBlack from "./fonts/Pretendard-Black.woff2";

// Bundled so renders look the same on every PC (Windows otherwise falls back to Malgun Gothic).
// Pretendard is SIL OFL 1.1 — see fonts/LICENSE-Pretendard.txt.
export const SHORTS_FONT = '"Pretendard Shorts", "Malgun Gothic", "Apple SD Gothic Neo", sans-serif';

const fontHandle = delayRender("Loading Pretendard Black");
const face = new FontFace("Pretendard Shorts", `url(${pretendardBlack}) format("woff2")`, { weight: "900" });
face
  .load()
  .then((loaded) => {
    document.fonts.add(loaded);
    continueRender(fontHandle);
  })
  .catch((err) => {
    console.error("font load failed, using fallback", err);
    continueRender(fontHandle);
  });

interface OutlinedProps {
  readonly children: React.ReactNode;
  readonly outline: number;
  readonly style: React.CSSProperties;
}

/**
 * Thick outline that renders the same everywhere: a stroked copy underneath, the clean fill on top.
 * (-webkit-text-stroke alone eats into the glyph, and paint-order isn't reliable for HTML text.)
 */
export const Outlined: React.FC<OutlinedProps> = ({ children, outline, style }) => (
  <div style={{ ...style, position: "relative" }}>
    <div aria-hidden style={{ WebkitTextStroke: `${outline * 2}px #000`, color: "#000", textShadow: "0 6px 18px rgba(0,0,0,0.7)" }}>
      {children}
    </div>
    <div style={{ position: "absolute", inset: 0 }}>{children}</div>
  </div>
);
