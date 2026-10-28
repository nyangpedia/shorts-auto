import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "../src/App";
import * as api from "../src/api";
import type { Project, ReferenceState, ScriptsState, ProductionState } from "../src/types";

vi.mock("../src/api");

const project: Project = {
  project_id: "261011_2130",
  project_title: "untitled",
  display_name: "261011_untitled",
  created_at: "2026-10-11T21:30:00",
  updated_at: "2026-10-11T21:30:00",
  current_step: "Reference",
  step_statuses: [],
  selected_reference_path: null,
  selected_candidate_id: null,
  settings_snapshot: {},
  job_history: [],
  generated_files: {}
};

const emptyReference: ReferenceState = { candidates: [], selected_reference: null, reference_script: null, analysis: null, analysis_markdown: null };
const emptyScripts: ScriptsState = { candidates: [], selected_candidate: null, final_script: null, feedback: "", tts_validation: null };
const emptyProduction: ProductionState = { has_audio: false, audio_filename: null, duration_seconds: null, has_scene_data: false, scene_count: 0, scenes: [] };

const mocked = vi.mocked(api);

describe("App", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    window.history.replaceState(null, "", `/?project=${project.project_id}`);
    mocked.fetchProjects.mockResolvedValue([project]);
    mocked.fetchReferenceState.mockResolvedValue(emptyReference);
    mocked.fetchScriptsState.mockResolvedValue(emptyScripts);
    mocked.fetchProductionState.mockResolvedValue(emptyProduction);
    mocked.getProject.mockResolvedValue(project);
    mocked.fetchUsage.mockResolvedValue({ llm: 3, llm_limit: 100, image: 0, image_limit: 200, tts: 1 });
    mocked.fetchTopics.mockResolvedValue({ topics: [] });
    mocked.fetchDaily.mockResolvedValue({ keywords: [], fetched_on: null, items: [] });
  });

  it("opens on the home screen and continues a project from it", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", "/");
    render(<App />);

    expect(await screen.findByRole("heading", { name: "이어서 만들기" })).toBeInTheDocument();
    const [, fromHome] = screen.getAllByRole("button", { name: /261011_untitled/ }); // rail entry, then the home card
    await user.click(fromHome);
    expect(await screen.findByRole("heading", { name: "제목 없음" })).toBeInTheDocument();
  });

  it("starts a saved topic as a new project and writes drafts for it", async () => {
    const user = userEvent.setup();
    const topic = { id: "261011_2130:1", source_project_id: "261011_2130", reference_title: "원본", title: "주제 둘", hook: "훅", category: "상식 파괴", analyzed_at: "2026-10-27T10:00", used_by: null };
    const created = { ...project, project_id: "261011_2140", project_title: "주제 둘" };
    mocked.fetchTopics.mockResolvedValue({ topics: [topic] });
    mocked.startTopic.mockResolvedValue({ project: created, feedback: "2번 추천 주제로 작성: 주제 둘" });
    mocked.getProject.mockResolvedValue(created);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: /주제 창고/ }));
    await user.click(await screen.findByRole("button", { name: "이 주제로 만들기" }));

    await waitFor(() => expect(mocked.generateScriptCandidates).toHaveBeenCalledWith("261011_2140", "2번 추천 주제로 작성: 주제 둘"));
    expect(await screen.findByRole("heading", { name: "주제 둘" })).toBeInTheDocument();
  });
  afterEach(() => cleanup());

  it("creates a project without a browser prompt and opens the title field", async () => {
    const user = userEvent.setup();
    const promptSpy = vi.spyOn(window, "prompt");
    mocked.createProject.mockResolvedValue({ ...project, project_id: "261011_2131", display_name: "261011_2131_untitled" });
    render(<App />);

    await screen.findByRole("heading", { name: "제목 없음" });
    await user.click(screen.getByRole("button", { name: "+ 새 프로젝트" }));

    await waitFor(() => expect(mocked.createProject).toHaveBeenCalledWith("untitled"));
    expect(screen.getByRole("textbox", { name: "프로젝트 제목" })).toHaveFocus();
    expect(promptSpy).not.toHaveBeenCalled();
  });

  it("saves an edited title with Enter", async () => {
    const user = userEvent.setup();
    mocked.updateProject.mockResolvedValue({ ...project, project_title: "피라미드" });
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "✎ 제목 수정" }));
    await user.type(screen.getByRole("textbox", { name: "프로젝트 제목" }), "피라미드{Enter}");

    await waitFor(() => expect(mocked.updateProject).toHaveBeenCalledWith(project.project_id, { project_title: "피라미드" }));
    expect(await screen.findByRole("heading", { name: "피라미드" })).toBeInTheDocument();
  });

  it("starts on the reference step and searches 50 shorts at a time", async () => {
    const user = userEvent.setup();
    mocked.searchReferences.mockResolvedValue({ candidates: [] } as never);
    render(<App />);

    await user.type(await screen.findByRole("textbox", { name: "검색어" }), "문어");
    await user.click(screen.getByRole("button", { name: "검색" }));

    await waitFor(() => expect(mocked.searchReferences).toHaveBeenCalled());
    expect(mocked.searchReferences.mock.calls[0][1]).toMatchObject({ keyword: "문어", max_results: 50, duration_filter: "under_180" });
    expect(screen.getByRole("button", { name: /다음: 분석/ })).toBeDisabled();
  });

  it("runs audio, transcript and analysis in one click", async () => {
    const user = userEvent.setup();
    const withReference = { ...emptyReference, selected_reference: { video_id: "v1", title: "레퍼런스" } as never };
    mocked.fetchReferenceState.mockResolvedValue(withReference);
    render(<App />);

    await user.click(await screen.findByRole("button", { name: "분석 시작" }));

    await waitFor(() => expect(mocked.runReferenceAnalysis).toHaveBeenCalled());
    expect(mocked.extractReferenceAudio).toHaveBeenCalled();
    expect(mocked.runReferenceStt).toHaveBeenCalled();
    expect(mocked.extractReferenceAudio.mock.invocationCallOrder[0]).toBeLessThan(mocked.runReferenceAnalysis.mock.invocationCallOrder[0]);
  });
});
