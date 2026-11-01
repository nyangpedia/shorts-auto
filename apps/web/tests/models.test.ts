import { describe, expect, it } from "vitest";

import { recommendStyles } from "../src/models";

describe("recommendStyles", () => {
  it("points a what-if disaster topic at cinematic and an animal topic at nature", () => {
    expect(recommendStyles("만약 지구에서 사람이 5초간 사라진다면")[0]).toBe("cinematic");
    expect(recommendStyles("바다 깊은 곳 동물의 비밀")[0]).toBe("nature_doc");
  });

  it("returns at most two and nothing when no word matches", () => {
    expect(recommendStyles("만약 우주에서 과학 실험 역사 게임").length).toBe(2);
    expect(recommendStyles("오늘 점심 뭐 먹지")).toEqual([]);
  });
});
