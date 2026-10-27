import type { ProductionState, ReferenceState, ScriptsState } from "./types";

export const STEPS: readonly { title: string; sub: string }[] = [
  { title: "레퍼런스", sub: "참고 쇼츠 선택" },
  { title: "분석", sub: "성공 공식·주제" },
  { title: "대본", sub: "초안·다듬기·사실 확인" },
  { title: "음성·화풍", sub: "내레이션·씬 구성" },
  { title: "이미지·영상", sub: "씬별 제작" },
  { title: "완성", sub: "렌더링·업로드" }
];

export type StepNumber = 1 | 2 | 3 | 4 | 5 | 6;

/**
 * Furthest step that has something to show, judged from the latest artifact that exists
 * (a project started from an uploaded audio file has analysis but no selected reference).
 */
export function reachedStep(
  reference: ReferenceState | null,
  scripts: ScriptsState | null,
  production: ProductionState | null
): StepNumber {
  const scenes = production?.video_scenes ?? [];
  if (scenes.length > 0 && scenes.every((scene) => scene.start_image_url)) return 6;
  if (production?.has_audio && scenes.length > 0) return 5;
  if (scripts?.final_script) return 4;
  if (scripts?.candidates.length) return 3;
  if (reference?.selected_reference || reference?.reference_script || reference?.analysis) return 2;
  return 1;
}
