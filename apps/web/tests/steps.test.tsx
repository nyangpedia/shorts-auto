import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FinalStep } from "../src/components/FinalStep";
import { ScenesStep } from "../src/components/ScenesStep";
import { ScriptStep } from "../src/components/ScriptStep";
import type { ScriptCandidate, VideoSceneItem } from "../src/types";
import { reachedStep } from "../src/wizard";

afterEach(() => {
  cleanup();
  localStorage.clear();
});

const candidate = { candidate_id: "draft_a", candidate_type: "draft_a", title: "초안 A", draft_script: "초안 본문" } as ScriptCandidate;

function scene(id: number, image: boolean, video: boolean): VideoSceneItem {
  return {
    scene_id: id,
    narration: `씬 ${id} 내레이션`,
    start_image_url: image ? `/img/${id}.png` : null,
    generated_video_url: video ? `/vid/${id}.mp4` : null,
    start_image_prompt: "",
    video_prompt: ""
  } as unknown as VideoSceneItem;
}

describe("reachedStep", () => {
  it("uses the furthest artifact, even without a selected reference", () => {
    const reference = { candidates: [], selected_reference: null, reference_script: "자막", analysis: {}, analysis_markdown: null };
    expect(reachedStep(reference, null, null)).toBe(2);
    expect(reachedStep(null, { final_script: "대본" } as never, null)).toBe(4);
    expect(reachedStep(null, null, { has_audio: true, video_scenes: [scene(1, false, false)] } as never)).toBe(5);
    expect(reachedStep(null, null, { has_audio: true, video_scenes: [scene(1, true, false)] } as never)).toBe(6);
  });
});

describe("ScriptStep", () => {
  const base = {
    candidates: [candidate],
    selectedCandidateId: "draft_a",
    finalScript: "피라미드는 노예가 지었다.",
    ttsValidation: null,
    isBusy: false,
    busyText: null,
    onSelect: vi.fn(),
    onFinalize: vi.fn(),
    onFactCheck: vi.fn()
  };

  it("saves only after editing and blocks fact check on unsaved text", async () => {
    const user = userEvent.setup();
    const onSave = vi.fn();
    render(<ScriptStep {...base} factCheck={null} onSave={onSave} />);

    const save = screen.getByRole("button", { name: "저장" });
    expect(save).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "최종 대본" }), " 수정");
    expect(screen.getByRole("button", { name: "AI 사실 확인" })).toBeDisabled();
    await user.click(save);
    expect(onSave).toHaveBeenCalledWith("피라미드는 노예가 지었다. 수정");
  });

  it("lists claims and selects the quoted text in the editor", async () => {
    const user = userEvent.setup();
    const factCheck = {
      script_hash: "x",
      claims: [{ quote: "노예가 지었다", verdict: "의심" as const, reason: "임금 노동자가 정설", search_query: "피라미드 노동자" }]
    };
    render(<ScriptStep {...base} factCheck={factCheck} onSave={vi.fn()} />);

    expect(screen.getByText("확인 필요 1곳")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "검색 ↗" })).toHaveAttribute("href", expect.stringContaining("google.com/search"));
    await user.click(screen.getByText("노예가 지었다"));
    const editor = screen.getByRole("textbox", { name: "최종 대본" }) as HTMLTextAreaElement;
    expect(editor.value.slice(editor.selectionStart, editor.selectionEnd)).toBe("노예가 지었다");
  });
});

describe("ScenesStep", () => {
  it("makes videos only for scenes that have an image but no video", async () => {
    const user = userEvent.setup();
    const onGenerateVideo = vi.fn().mockResolvedValue(undefined);
    render(
      <ScenesStep
        isBusy={false}
        onGenerateAllImages={vi.fn()}
        onGenerateImage={vi.fn()}
        onGenerateVideo={onGenerateVideo}
        onRegenerate={vi.fn()}
        onUpdatePrompts={vi.fn()}
        scenes={[scene(1, true, true), scene(2, true, false), scene(3, false, false)]}
      />
    );

    await user.click(screen.getByRole("button", { name: "남은 영상 1개 만들기" }));
    await waitFor(() => expect(onGenerateVideo).toHaveBeenCalledTimes(1));
    expect(onGenerateVideo).toHaveBeenCalledWith(2, "kenburns");
  });
});

describe("FinalStep", () => {
  it("remembers the upload checklist per project", async () => {
    const user = userEvent.setup();
    const props = {
      projectId: "p1",
      finalVideoUrl: null,
      candidate: null,
      videoTitle: "",
      scenesReady: true,
      isBusy: false,
      busyText: null,
      onTitleChange: vi.fn(),
      onRender: vi.fn()
    };
    const { unmount } = render(<FinalStep {...props} />);
    await user.click(screen.getAllByRole("checkbox")[0]);
    unmount();

    render(<FinalStep {...props} />);
    expect(screen.getAllByRole("checkbox")[0]).toBeChecked();
    expect(screen.getByText("1/4")).toBeInTheDocument();
  });
});
