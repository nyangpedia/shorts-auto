import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";

const signOut = vi.fn();
vi.mock("../src/supabase", () => ({
  supabase: { auth: { getSession: () => Promise.resolve({ data: { session: { user: { email: "me@example.com" } } } }), signOut } }
}));

import { AccountBox } from "../src/components/LoginGate";

afterEach(cleanup);

it("shows who is signed in and signs out from the sidebar", async () => {
  render(<AccountBox />);
  await waitFor(() => expect(screen.getByText("me@example.com")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: "로그아웃" }));
  expect(signOut).toHaveBeenCalled();
});
