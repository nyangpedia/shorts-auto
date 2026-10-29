export interface ModelChoice {
  readonly id: string;
  readonly name: string;
  readonly free: boolean;
}

export const IMAGE_MODELS: readonly ModelChoice[] = [
  { id: "cloudflare", name: "Cloudflare FLUX", free: true },
  { id: "nano_banana_pro", name: "Nano Banana Pro (Higgsfield)", free: false },
  { id: "gpt_image_2", name: "GPT Image 2 (Higgsfield)", free: false },
  { id: "seedream_v5_pro", name: "Seedream 5.0 Pro (Higgsfield)", free: false },
  { id: "gemini_image", name: "Gemini 이미지", free: false },
  { id: "gpt_image", name: "GPT Image 2.5 Sunburst (OpenAI)", free: false }
];

export const VIDEO_MODELS: readonly ModelChoice[] = [
  { id: "parallax", name: "2.5D 입체 모션", free: true },
  { id: "kenburns", name: "카메라 모션 (빠름)", free: true },
  { id: "kling_o3_flf", name: "Kling 3.0 (Higgsfield)", free: false },
  { id: "minimax_h3", name: "Minimax H3 (Higgsfield)", free: false },
  { id: "grok_video_v15_lite", name: "Grok Imagine Lite (Higgsfield)", free: false },
  { id: "seedance_2_0", name: "Seedance 2.0 (Higgsfield)", free: false },
  { id: "veo3_1", name: "Veo 3.1 (Higgsfield)", free: false }
];

// Keep ids in sync with VISUAL_STYLES in apps/api/app/production/styles.py.
export const VISUAL_STYLES = [
  { id: "claymation", label: "3D 클레이", blurb: "귀엽고 또렷함 · 무엇이든 무난" },
  { id: "flat", label: "플랫 인포그래픽", blurb: "깔끔한 설명 그래픽 · 원리·숫자" },
  { id: "cinematic", label: "시네마틱 실사", blurb: "영화 같은 긴장감 · 만약에·재난" },
  { id: "webtoon", label: "웹툰풍", blurb: "만화 컷 느낌 · 썰·이야기" },
  { id: "isometric", label: "미니어처", blurb: "작은 모형 세상 · 규모 비교" },
  { id: "watercolor", label: "수채화 애니", blurb: "부드러운 감성 · 명언·힐링" },
  { id: "vintage", label: "빈티지 사진", blurb: "어두운 옛 사진 · 역사·미스터리" },
  { id: "anime", label: "일본 애니", blurb: "셀 애니메이션 · 썰·심리" },
  { id: "brick", label: "브릭 장난감", blurb: "조립 블록 미니어처 · 사건 재현" },
  { id: "pixel", label: "레트로 픽셀", blurb: "16비트 게임 화면 · 만약에·게임" },
  { id: "papercraft", label: "종이 공예", blurb: "오린 종이 입체 · 설명·동화" },
  { id: "nature_doc", label: "다큐 자연 사진", blurb: "자연 다큐 느낌 · 동물·바다·우주" }
] as const;

export const modelLabel = (m: ModelChoice) => `${m.name} · ${m.free ? "무료" : "유료"}`;
