/* Tests for ProtectedRoute entity validation gate. */

import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { getEntity } from "@/api/entity";
import { ProtectedRoute } from "@/router";
import { useAppStore } from "@/stores/app";
import type { UserProfile } from "@/types";

vi.mock("@/api/entity", () => ({
  getEntity: vi.fn(),
}));

vi.mock("@/components/layout/main-layout", () => ({
  MainLayout: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="main-layout">{children}</div>
  ),
}));

const MOCK_USER: UserProfile = {
  entity_uid: "test-uid-123",
  name: "Test User",
  kind: "human",
  host_url: "http://localhost:7001",
};

function renderProtectedRoute() {
  return render(
    <MemoryRouter initialEntries={["/protected"]}>
      <Routes>
        <Route path="/" element={<div data-testid="login-page">Login</div>} />
        <Route
          path="/protected"
          element={
            <ProtectedRoute>
              <div data-testid="protected-content">Protected</div>
            </ProtectedRoute>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAppStore.setState({
      currentUser: null,
      currentHostUid: null,
      contacts: [],
      contactStatusMap: {},
      contactUnreadMap: {},
      unreadMessageIds: {},
      avatarCache: {},
      activeChatUid: null,
      carbonCopyMessages: [],
    });
  });

  it("redirects to login when no currentUser", () => {
    renderProtectedRoute();
    expect(screen.getByTestId("login-page")).toBeInTheDocument();
  });

  it("renders children after entity verification succeeds", async () => {
    vi.mocked(getEntity).mockResolvedValueOnce({} as never);
    useAppStore.setState({ currentUser: MOCK_USER });

    renderProtectedRoute();

    await waitFor(() => {
      expect(screen.getByTestId("protected-content")).toBeInTheDocument();
    });
    expect(getEntity).toHaveBeenCalledWith("test-uid-123");
  });

  it("calls logout when entity verification fails (stale localStorage)", async () => {
    vi.mocked(getEntity).mockRejectedValueOnce(new Error("Not found"));
    useAppStore.setState({ currentUser: MOCK_USER });

    renderProtectedRoute();

    await waitFor(() => {
      expect(screen.getByTestId("login-page")).toBeInTheDocument();
    });
    expect(useAppStore.getState().currentUser).toBeNull();
  });
});
