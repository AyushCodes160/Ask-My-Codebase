// ============================================================
// FILE: frontend/src/main.jsx
// PURPOSE: React app entry point — mounts App into the DOM.
// ============================================================

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <App />
  </StrictMode>
);
