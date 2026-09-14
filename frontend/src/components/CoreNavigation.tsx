type CorePage =
  | "dashboard"
  | "processing"
  | "systems"
  | "services"
  | "incidents"
  | "memory";

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

export default function CoreNavigation({
  page,
  onNavigate,
}: {
  page: CorePage;
  onNavigate: (path: string) => void;
}) {
  return (
    <nav className="core-navigation" aria-label="C.O.R.E. console navigation">
      <div className="core-navigation-brand">
        <span>CYBERTRON</span>
        <strong>C.O.R.E.</strong>
      </div>

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
    </nav>
  );
}

export type { CorePage };
