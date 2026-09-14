import { useCallback, useEffect, useState } from "react";

import CoreNavigation, {
  type CorePage,
} from "./components/CoreNavigation";
import VoiceAgent3D, {
  type VoiceAgentRuntimeState,
} from "./components/VoiceAgent3D";
import DashboardPage from "./pages/DashboardPage";
import IncidentsPage from "./pages/IncidentsPage";
import MemoryPage from "./pages/MemoryPage";
import ProcessingPage from "./pages/ProcessingPage";
import ServicesPage from "./pages/ServicesPage";
import SystemsPage from "./pages/SystemsPage";
import "./core-shell.css";

function pageFromPath(pathname: string): CorePage {
  if (pathname.startsWith("/processing")) return "processing";
  if (pathname.startsWith("/systems")) return "systems";
  if (pathname.startsWith("/services")) return "services";
  if (pathname.startsWith("/incidents")) return "incidents";
  if (pathname.startsWith("/memory")) return "memory";
  return "dashboard";
}

const PAGE_TITLES: Record<CorePage, string> = {
  dashboard: "Dashboard",
  processing: "Processing",
  systems: "Systems",
  services: "Services",
  incidents: "Incidents",
  memory: "Memory",
};

const INITIAL_VOICE_AGENT_STATE: VoiceAgentRuntimeState = {
  activeAgent: "STANDBY",
  activeTool: "NONE",
  activeModel: "UNKNOWN",
  orchestrationState: "IDLE",
  speechAnalyser: null,
  voiceState: "OFFLINE",
};

export default function CoreConsole() {
  const [page, setPage] = useState<CorePage>(() =>
    pageFromPath(window.location.pathname),
  );
  const [voiceAgentState, setVoiceAgentState] = useState<VoiceAgentRuntimeState>(
    INITIAL_VOICE_AGENT_STATE,
  );
  const updateVoiceAgentState = useCallback((state: VoiceAgentRuntimeState) => {
    setVoiceAgentState(state);
  }, []);

  useEffect(() => {
    document.body.dataset.corePage = page;
    document.title = `C.O.R.E. — ${PAGE_TITLES[page]}`;

    return () => {
      delete document.body.dataset.corePage;
    };
  }, [page]);

  useEffect(() => {
    if (page === "dashboard") return;

    setVoiceAgentState((current) => ({
      ...current,
      orchestrationState: "IDLE",
      speechAnalyser: null,
      voiceState: current.voiceState === "OFFLINE" ? "OFFLINE" : "READY",
    }));
  }, [page]);

  useEffect(() => {
    const handlePopState = () => {
      setPage(pageFromPath(window.location.pathname));
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  function navigate(path: string) {
    if (window.location.pathname !== path) {
      window.history.pushState({}, "", path);
    }

    setPage(pageFromPath(path));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  return (
    <>
      <CoreNavigation page={page} onNavigate={navigate} />
      <VoiceAgent3D {...voiceAgentState} />
      {page === "dashboard" && (
        <DashboardPage onVoiceAgentStateChange={updateVoiceAgentState} />
      )}
      {page === "processing" && <ProcessingPage />}
      {page === "systems" && <SystemsPage />}
      {page === "services" && <ServicesPage />}
      {page === "incidents" && <IncidentsPage />}
      {page === "memory" && <MemoryPage />}
    </>
  );
}
