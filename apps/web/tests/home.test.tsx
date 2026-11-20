import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { HomeView } from "../src/components/HomeView";

afterEach(cleanup);

const base = { projects: [], topicsLeft: 0, stepLabel: () => "", onNew: vi.fn(), onOpen: vi.fn(), onGo: vi.fn(), missingKeys: 0 };

it("lists what other PCs made, and hides the section when there is nothing", () => {
  const { rerender } = render(<HomeView {...base} />);
  expect(screen.queryByText("다른 PC에서 만든 작업")).not.toBeInTheDocument();

  rerender(<HomeView {...base} otherPcs={[{ project_id: "261101_0900", title: "집에서 만든 것", step: "완성", rendered: true, uploaded: false, archived: false, device: "HOME", updated_at: "2026-11-01T09:00:00+00:00" }]} />);
  expect(screen.getByText("다른 PC에서 만든 작업")).toBeInTheDocument();
  expect(screen.getByText("집에서 만든 것")).toBeInTheDocument();
  expect(screen.getByText(/렌더링 완료 · HOME/)).toBeInTheDocument();
});
