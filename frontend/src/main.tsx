import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import CognitionGraph from "./components/CognitionGraph";

const root = document.getElementById("root");

if (!root) {
  throw new Error("CyberTron root element not found");
}

createRoot(root).render(
  <StrictMode>
    <div
      style={{
        width: "min(1180px, calc(100% - 32px))",
        margin: "24px auto 0",
      }}
    >
      <CognitionGraph />
    </div>
    <App />
  </StrictMode>
);
