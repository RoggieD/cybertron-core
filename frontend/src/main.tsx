import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import CoreConsole from "./CoreConsole";

const root = document.getElementById("root");

if (!root) {
  throw new Error("CyberTron root element not found");
}

createRoot(root).render(
  <StrictMode>
    <CoreConsole />
  </StrictMode>
);
