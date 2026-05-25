import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import "@/styles/globals.css";
import { AppRouter } from "@/router";

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <AppRouter />
    </StrictMode>,
  );
}
