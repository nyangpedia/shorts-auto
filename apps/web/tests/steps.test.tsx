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
    onFactCheck: vi.fn(),
    similarity: null,
    videoTitle: "untitled",
    onUseTitle: vi.fn()
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

describe("ScriptStep title options", () => {
  it("lets the user pick a recommended title as the project/opening title", async () => {
    const user = userEvent.setup();
    const onUseTitle = vi.fn();
    const withTitles = { ...candidate, title_options: ["문어는 심장이 3개?", "파란 피의 비밀"] } as ScriptCandidate;
    render(<ScriptStep candidates={[withTitles]} selectedCandidateId="draft_a" finalScript={null} factCheck={null} similarity={null} ttsValidation={null} isBusy={false} busyText={null} onSelect={vi.fn()} onFinalize={vi.fn()} onSave={vi.fn()} onFactCheck={vi.fn()} videoTitle="" onUseTitle={onUseTitle} />);
    await user.click(screen.getByRole("button", { name: "파란 피의 비밀" }));
    expect(onUseTitle).toHaveBeenCalledWith("파란 피의 비밀");
  });
});

describe("ScriptStep similarity", () => {
  it("shows the overlap level and the copied sentence", () => {
    const similarity = { score: 0.42, level: "높음" as const, comparable: true, sentences: [{ text: "피라미드는 노예가 지었다.", score: 0.9 }] };
    render(<ScriptStep candidates={[candidate]} selectedCandidateId="draft_a" finalScript="피라미드는 노예가 지었다." factCheck={null} similarity={similarity} ttsValidation={null} isBusy={false} busyText={null} onSelect={vi.fn()} onFinalize={vi.fn()} onSave={vi.fn()} onFactCheck={vi.fn()} videoTitle="" onUseTitle={vi.fn()} />);
    expect(screen.getByText("높음 · 42%")).toBeInTheDocument();
    expect(screen.getByText("원본과 거의 같음")).toBeInTheDocument();
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
        onChangeStyle={vi.fn()}
        onUpdatePrompts={vi.fn()}
        scenes={[scene(1, true, true), scene(2, true, false), scene(3, false, false)]}
        styleId="claymation"
      />
    );

    await user.click(screen.getByRole("button", { name: "남은 영상 1개 만들기" }));
    await waitFor(() => expect(onGenerateVideo).toHaveBeenCalledTimes(1));
    expect(onGenerateVideo).toHaveBeenCalledWith(2, "kenburns");
  });

  it("shows the applied style and re-plans scenes only after confirming a change", async () => {
    const user = userEvent.setup();
    const onChangeStyle = vi.fn();
    const confirm = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    render(
      <ScenesStep
        isBusy={false}
        onChangeStyle={onChangeStyle}
        onGenerateAllImages={vi.fn()}
        onGenerateImage={vi.fn()}
        onGenerateVideo={vi.fn()}
        onRegenerate={vi.fn()}
        onUpdatePrompts={vi.fn()}
        scenes={[scene(1, true, false)]}
        styleId="claymation"
      />
    );
    await user.click(screen.getByRole("button", { name: /3D 클레이/ })); // shows the applied style; opens the cards
    expect(screen.getByRole("radio", { name: /3D 클레이/ })).toHaveAttribute("aria-checked", "true");

    await user.click(screen.getByRole("radio", { name: /시네마틱 실사/ }));
    expect(onChangeStyle).not.toHaveBeenCalled(); // declined
    await user.click(screen.getByRole("radio", { name: /시네마틱 실사/ }));
    expect(onChangeStyle).toHaveBeenCalledWith("cinematic");
    expect(confirm.mock.calls[0][0]).toContain("이미지 1장");
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
      onRender: vi.fn(),
      onOpenSettings: vi.fn(),
      scenePictures: [],
      thumbnailUrl: null
    };
    const { unmount } = render(<FinalStep {...props} />);
    await user.click(screen.getAllByRole("checkbox")[0]);
    unmount();

    render(<FinalStep {...props} />);
    expect(screen.getAllByRole("checkbox")[0]).toBeChecked();
    expect(screen.getByText("1/4")).toBeInTheDocument();
  });
});
