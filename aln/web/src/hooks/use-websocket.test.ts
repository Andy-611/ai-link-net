/* Tests for useWebSocket reconnect behavior. */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";

import { useAppStore } from "@/stores/app";
import type { UserProfile } from "@/types";

vi.mock("@/api", () => ({
  wsBaseUrl: () => "ws://localhost:7001/",
}));

const MOCK_USER: UserProfile = {
  entity_uid: "ws-test-uid",
  name: "WS User",
  kind: "human",
  host_url: "http://localhost:7001",
};

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  readyState = 1;
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onclose: ((e: { code: number; reason: string }) => void) | null = null;
  onerror: (() => void) | null = null;

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }
  send = vi.fn();
  close = vi.fn(() => {
    this.readyState = 3;
    this.onclose?.({ code: 1000, reason: "" });
  });

  simulateClose(code: number) {
    this.readyState = 3;
    this.onclose?.({ code, reason: "" });
  }

  static OPEN = 1;
}

describe("useWebSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket);
    useAppStore.setState({ currentUser: MOCK_USER, activeChatUid: null });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    useAppStore.setState({ currentUser: null });
  });

  it("connects with currentUser entity_uid", async () => {
    const { useWebSocket } = await import("@/hooks/use-websocket");
    renderHook(() => useWebSocket());
    await act(() => vi.advanceTimersByTimeAsync(0));

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe(
      "ws://localhost:7001/api/v1/ws/messages/ws-test-uid",
    );
  });

  it("does not connect when currentUser is null", async () => {
    useAppStore.setState({ currentUser: null });
    const { useWebSocket } = await import("@/hooks/use-websocket");
    renderHook(() => useWebSocket());
    await act(() => vi.advanceTimersByTimeAsync(0));

    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("reconnects on normal close", async () => {
    const { useWebSocket } = await import("@/hooks/use-websocket");
    renderHook(() => useWebSocket());
    await act(() => vi.advanceTimersByTimeAsync(0));

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateClose(1000));
    await act(() => vi.advanceTimersByTimeAsync(3000));

    expect(MockWebSocket.instances).toHaveLength(2);
  });

  it("does NOT reconnect on code 1008 (entity not found)", async () => {
    const { useWebSocket } = await import("@/hooks/use-websocket");
    renderHook(() => useWebSocket());
    await act(() => vi.advanceTimersByTimeAsync(0));

    const ws = MockWebSocket.instances[0];
    act(() => ws.simulateClose(1008));
    await act(() => vi.advanceTimersByTimeAsync(5000));

    expect(MockWebSocket.instances).toHaveLength(1);
  });
});
