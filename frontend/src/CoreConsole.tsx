import { useEffect, useState } from "react";

import App from "./App";
import CoreNavigation, {
  type CorePage,
} from "./components/CoreNavigation";
import DashboardPage from "./pages/DashboardPage";
import ProcessingPage from "./pages/ProcessingPage";
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

export default function CoreConsole() {
  const [page, setPage] = useState<CorePage>(() =>
    pageFromPath(window.location.pathname),
  );

  useEffect(() => {
    document.body.dataset.corePage = page;
    document.title = `C.O.R.E. — ${PAGE_TITLES[page]}`;

    return () => {
      delete document.body.dataset.corePage;
    };
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

  const usesLegacyApp =
    page === "services" || page === "incidents" || page === "memory";

  return (
    <>
      <CoreNavigation page={page} onNavigate={navigate} />

      {page === "dashboard" && <DashboardPage />}
      {page === "processing" && <ProcessingPage />}
      {page === "systems" && <SystemsPage />}
      {usesLegacyApp && <App />}
    </>
  );
}
