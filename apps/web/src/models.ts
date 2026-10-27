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
  { id: "dall-e-3", name: "DALL-E 3 (OpenAI)", free: false }
];

export const VIDEO_MODELS: readonly ModelChoice[] = [
  { id: "kenburns", name: "카메라 모션", free: true },
  { id: "kling_o3_flf", name: "Kling 3.0 (Higgsfield)", free: false },
  { id: "minimax_h3", name: "Minimax H3 (Higgsfield)", free: false },
  { id: "grok_video_v15_lite", name: "Grok Imagine Lite (Higgsfield)", free: false },
  { id: "seedance_2_0", name: "Seedance 2.0 (Higgsfield)", free: false },
  { id: "veo3_1", name: "Veo 3.1 (Higgsfield)", free: false }
];

// Keep ids in sync with VISUAL_STYLES in apps/api/app/production/styles.py.
export const VISUAL_STYLES = [
  { id: "claymation", label: "3D 클레이" },
  { id: "flat", label: "플랫 인포그래픽" },
  { id: "cinematic", label: "시네마틱 실사" },
  { id: "webtoon", label: "웹툰풍" },
  { id: "isometric", label: "미니어처" },
  { id: "watercolor", label: "수채화 애니" },
  { id: "vintage", label: "빈티지 사진" }
] as const;

export const modelLabel = (m: ModelChoice) => `${m.name} · ${m.free ? "무료" : "유료"}`;
