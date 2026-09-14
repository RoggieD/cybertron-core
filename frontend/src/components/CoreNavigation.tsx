import { useEffect, useState } from "react";

type CorePage =
  | "dashboard"
  | "processing"
  | "systems"
  | "services"
  | "incidents"
  | "memory";

type CoreTheme = "cyan" | "neon-green";

type NavItem = {
  id: CorePage;
  label: string;
  path: string;
};

const NAV_ITEMS: NavItem[] = [
  { id: "dashboard", label: "DASHBOARD", path: "/" },
  { id: "processing", label: "PROCESSING", path: "/processing" },
  { id: "systems", label: "SYSTEMS", path: "/systems" },
  { id: "services", label: "SERVICES", path: "/services" },
  { id: "incidents", label: "INCIDENTS", path: "/incidents" },
  { id: "memory", label: "MEMORY", path: "/memory" },
];

const THEME_STORAGE_KEY = "cybertron-core-theme";

function initialTheme(): CoreTheme {
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  return saved === "cyan" || saved === "neon-green"
    ? saved
    : "neon-green";
}

export default function CoreNavigation({
  page,
  onNavigate,
}: {
  page: CorePage;
  onNavigate: (path: string) => void;
}) {
  const [theme, setTheme] = useState<CoreTheme>(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.coreTheme = theme;
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  return (
    <nav className="core-navigation" aria-label="C.O.R.E. console navigation">
      <div className="core-navigation-brand">
        <span>CYBERTRON</span>
        <strong>C.O.R.E.</strong>
      </div>

      <div className="core-navigation-controls">
        <div className="core-navigation-links">
          {NAV_ITEMS.map((item) => (
            <button
              type="button"
              key={item.id}
              className={page === item.id ? "active" : ""}
              onClick={() => onNavigate(item.path)}
            >
              {item.label}
            </button>
          ))}
        </div>

        <div className="core-theme-picker" aria-label="GUI accent color">
          <span>COLOR</span>
          <button
            type="button"
            className={`theme-swatch cyan ${theme === "cyan" ? "active" : ""}`}
            onClick={() => setTheme("cyan")}
            aria-label="Use cyan theme"
            title="Cyan"
          />
          <button
            type="button"
            className={`theme-swatch neon-green ${theme === "neon-green" ? "active" : ""}`}
            onClick={() => setTheme("neon-green")}
            aria-label="Use neon green theme"
            title="Neon Green"
          />
        </div>
      </div>
    </nav>
  );
}

export type { CorePage };
