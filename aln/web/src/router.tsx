/* Application routes. */

import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { TooltipProvider } from "@/components/ui/tooltip";

import { getEntity } from "@/api";
import { useAppStore } from "@/stores/app";
import { MainLayout } from "@/components/layout/main-layout";
import { LoginPage } from "@/pages/login";
import { ChatPage } from "@/pages/chat";
import { DiscoverPage } from "@/pages/discover";
import { MyEntitiesPage } from "@/pages/entities";
import { TradePage } from "@/pages/trade";
import { ReputationPage } from "@/pages/reputation";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const currentUser = useAppStore((s) => s.currentUser);
  const forgetCurrentUser = useAppStore((s) => s.forgetCurrentUser);
  const [verified, setVerified] = useState(false);

  useEffect(() => {
    if (!currentUser) return;
    let cancelled = false;
    getEntity(currentUser.entity_uid)
      .then(() => {
        if (!cancelled) setVerified(true);
      })
      .catch(() => {
        if (!cancelled) forgetCurrentUser();
      });
    return () => { cancelled = true; };
  }, [currentUser, forgetCurrentUser]);

  if (!currentUser) return <Navigate to="/" replace />;
  if (!verified) return null;
  return <MainLayout>{children}</MainLayout>;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <TooltipProvider delayDuration={300}>
        <Routes>
          <Route path="/" element={<LoginPage />} />
          <Route
            path="/chat"
            element={
              <ProtectedRoute>
                <ChatPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/discover"
            element={
              <ProtectedRoute>
                <DiscoverPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/entities"
            element={
              <ProtectedRoute>
                <MyEntitiesPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/trade"
            element={
              <ProtectedRoute>
                <TradePage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reputation"
            element={
              <ProtectedRoute>
                <ReputationPage />
              </ProtectedRoute>
            }
          />
          {/* Legacy redirects */}
          <Route path="/portal" element={<Navigate to="/reputation" replace />} />
          <Route path="/observer" element={<Navigate to="/trade" replace />} />
          <Route path="/register" element={<Navigate to="/entities" replace />} />
          <Route path="/agents" element={<Navigate to="/entities" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </TooltipProvider>
    </BrowserRouter>
  );
}
