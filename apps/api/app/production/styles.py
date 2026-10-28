from __future__ import annotations

# Keep ids in sync with VISUAL_STYLES in apps/web/src/components/ProductionPanel.tsx.
VISUAL_STYLES: dict[str, dict[str, str]] = {
    "claymation": {
        "label": "3D 클레이메이션",
        "role": "3D 스톱모션 클레이메이션 비주얼 마스터",
        "style": "Cute professional miniature claymation infographic, handcrafted plasticine texture, visible fingerprints, stop-motion look, vivid rich studio lighting, macro photography",
        "subject": 'Depict people as a "tiny miniature clay figurine (approx. 2-3cm scale)" with dramatic scale contrast against giant surrounding objects',
        "texture": "macro photography details, visible handcrafted clay fingerprints, hand-molded plasticine textures, soft matte finish, shallow depth of field with creamy bokeh",
        "lighting": "cinematic studio lighting, soft rim highlights, deep tactile shadows",
        "motion": "smooth stop-motion animation",
    },
    "flat": {
        "label": "플랫 인포그래픽",
        "role": "모션그래픽 인포그래픽 아트 디렉터",
        "style": "Flat vector illustration, minimal geometric shapes, bold saturated colors, clean infographic style",
        "subject": "Depict people as simple flat vector characters with clear silhouettes; use iconic objects and diagrams-like compositions",
        "texture": "clean flat color fills, crisp edges, subtle grain, no photographic texture",
        "lighting": "flat even lighting with simple long shadows, high contrast color blocking",
        "motion": "smooth motion-graphics animation",
    },
    "cinematic": {
        "label": "시네마틱 실사",
        "role": "영화 촬영감독 출신 비주얼 디렉터",
        "style": "Cinematic photorealistic photography, dramatic moody lighting, 35mm film look",
        "subject": "Depict people as realistic adults with natural expressions, framed like a film still",
        "texture": "photorealistic detail, shallow depth of field, subtle film grain, anamorphic bokeh",
        "lighting": "dramatic low-key cinematic lighting, motivated practical lights, teal and orange grade",
        "motion": "smooth cinematic camera movement",
    },
    "webtoon": {
        "label": "웹툰풍",
        "role": "한국 웹툰 작화 감독",
        "style": "Korean webtoon style digital illustration, clean line art, soft cel shading",
        "subject": "Depict people as expressive webtoon characters with exaggerated emotional facial expressions",
        "texture": "clean confident line art, flat cel shading with soft gradients, manhwa panel composition",
        "lighting": "bright soft lighting with dramatic emotion-driven color accents",
        "motion": "smooth 2D animated motion",
    },
    "isometric": {
        "label": "아이소메트릭 미니어처",
        "role": "3D 아이소메트릭 디오라마 아티스트",
        "style": "Isometric 3D miniature diorama, tiny detailed world on a floating base, tilt-shift look",
        "subject": "Depict people as tiny stylized 3D figures inside a cut-away isometric diorama seen from a 45-degree top angle",
        "texture": "smooth stylized 3D render, soft materials, tilt-shift miniature depth of field",
        "lighting": "soft studio lighting, gentle ambient occlusion, pastel color palette",
        "motion": "smooth orbiting camera around the diorama",
    },
    "watercolor": {
        "label": "감성 수채화 애니",
        "role": "감성 애니메이션 배경 미술 감독",
        "style": "Warm watercolor anime illustration, soft pastel colors, hand-painted texture",
        "subject": "Depict people as gentle anime-style characters with soft expressions",
        "texture": "hand-painted watercolor washes, visible paper texture, soft edges",
        "lighting": "warm gentle sunlight, glowing highlights, dreamy atmosphere",
        "motion": "gentle drifting camera with soft parallax",
    },
    "vintage": {
        "label": "다크 빈티지 사진",
        "role": "역사 다큐멘터리 아카이브 비주얼 디렉터",
        "style": "Dark vintage black and white archival photograph, film grain, high contrast, mysterious mood",
        "subject": "Depict people as realistic figures in period-appropriate clothing, like found historical footage",
        "texture": "heavy film grain, scratches and dust, faded edges, silver gelatin print look",
        "lighting": "harsh high-contrast lighting with deep blacks, mysterious shadows",
        "motion": "slow documentary-style push-in",
    },
    "anime": {
        "label": "일본 애니",
        "role": "일본 TV 애니메이션 작화 감독",
        "style": "Japanese anime cel-shaded illustration, crisp line art, vivid colors, TV animation key frame",
        "subject": "Depict people as anime characters with large expressive eyes and clear emotional poses",
        "texture": "clean cel shading with hard shadow edges, painted anime background art",
        "lighting": "bright saturated lighting with dramatic rim light and sky gradients",
        "motion": "smooth 2D anime camera pan with parallax layers",
    },
    "brick": {
        "label": "브릭 장난감",
        "role": "조립 블록 장난감 스톱모션 감독",
        # Generic plastic building bricks — never a brand name, and no logos on studs.
        "style": "Plastic interlocking toy building bricks diorama, everything built from glossy bricks, toy photography",
        "subject": "Depict people as small plastic toy minifigures with simple painted faces and cylindrical heads",
        "texture": "glossy injection-molded plastic, plain studs without any logo, visible brick seams, macro toy photography",
        "lighting": "bright playful studio lighting with soft shadows, shallow depth of field",
        "motion": "smooth stop-motion brick animation",
    },
    "pixel": {
        "label": "레트로 픽셀",
        "role": "16비트 레트로 게임 픽셀 아티스트",
        "style": "Retro 16-bit pixel art, limited color palette, side-view game scene",
        "subject": "Depict people as small chunky pixel-art game sprites with readable silhouettes",
        "texture": "crisp square pixels, no anti-aliasing, dithered gradients, retro console look",
        "lighting": "flat game lighting with bold palette contrast",
        "motion": "smooth side-scrolling camera like a retro game",
    },
    "papercraft": {
        "label": "종이 공예",
        "role": "레이어드 페이퍼 아트 디오라마 작가",
        "style": "Layered paper-cut craft diorama, handmade cut paper shapes stacked in depth, papercraft",
        "subject": "Depict people as simple cut-paper figures with layered paper clothing",
        "texture": "visible paper fibers, crisp cut edges, layered depth with soft drop shadows between sheets",
        "lighting": "soft warm lighting casting gentle shadows between paper layers",
        "motion": "gentle camera drift revealing paper layers with parallax",
    },
    "nature_doc": {
        "label": "다큐 자연 사진",
        "role": "자연 다큐멘터리 촬영 감독",
        "style": "Nature documentary photography, natural colors, telephoto wildlife and landscape shot",
        "subject": "Depict people as real field researchers or explorers shown small within the natural scene",
        "texture": "photorealistic natural detail, crisp telephoto focus, natural film color",
        "lighting": "natural daylight or golden hour light, true-to-life atmosphere",
        "motion": "slow steady documentary camera move",
    },
}

DEFAULT_STYLE = "claymation"


def get_style(style_id: str | None) -> tuple[str, dict[str, str]]:
    sid = style_id or DEFAULT_STYLE
    if sid not in VISUAL_STYLES:
        raise ValueError(f"알 수 없는 화풍입니다: {sid}. 가능한 값: {', '.join(VISUAL_STYLES)}")
    return sid, VISUAL_STYLES[sid]
