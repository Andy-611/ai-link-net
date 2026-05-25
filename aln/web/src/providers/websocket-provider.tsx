/* Global WebSocket context — keeps WS alive across page navigation. */

import { createContext, useContext, type ReactNode } from "react";

import { useWebSocket, type WsEventListener } from "@/hooks/use-websocket";

type AddListener = (fn: WsEventListener) => () => void;

const WsContext = createContext<AddListener | null>(null);

export function WebSocketProvider({ children }: { children: ReactNode }) {
  const { addListener } = useWebSocket();
  return <WsContext.Provider value={addListener}>{children}</WsContext.Provider>;
}

export function useWsListener() {
  const addListener = useContext(WsContext);
  if (!addListener) throw new Error("useWsListener must be used within WebSocketProvider");
  return { addListener };
}
