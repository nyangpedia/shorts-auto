import "@testing-library/jest-dom/vitest";
import { render, screen, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProductionPanel } from "../src/components/ProductionPanel";
import type { ProductionState } from "../src/types";

const state = {
  has_audio: true,
  concept_kit: {
    visual_style: "Korean webtoon style",
    style_id: "webtoon",
    color_and_lighting: "",
    core_objects: [],
    camera_composition: "",
    continuity_rules: []
  },
  video_scenes: []
} as unknown as ProductionState;

describe("ProductionPanel style picker", () => {
  afterEach(() => cleanup());

  it("preselects the saved style and regenerates scenes with the chosen one", async () => {
    const user = userEvent.setup();
    const onGenerateConcepts = vi.fn();
    render(
      <ProductionPanel
        projectId="261026_1200"
        productionState={state}
        isBusy={false}
        hasFinalScript
        onGenerateProduction={() => {}}
        onGenerateConcepts={onGenerateConcepts}
      />
    );

    const select = screen.getByRole("combobox", { name: "화풍" });
    expect(select).toHaveValue("webtoon");
    expect(screen.getByText(/Visual Concept Kit \(웹툰풍\)/)).toBeInTheDocument();

    await user.selectOptions(select, "cinematic");
    await user.click(screen.getByRole("button", { name: "이 화풍으로 씬 다시 구성" }));
    expect(onGenerateConcepts).toHaveBeenCalledWith("cinematic");
  });
});
