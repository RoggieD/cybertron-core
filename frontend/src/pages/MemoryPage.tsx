import MemoryApprovalPanel from "../components/MemoryApprovalPanel";
import "../styles.css";

export default function MemoryPage() {
  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">PERSISTENT MEMORY</p>

        <h1>
          Memory <span>Governance</span>
        </h1>

        <p className="subtitle">
          Review, approve, reject, and audit proposed persistent memory changes.
        </p>
      </section>

      <MemoryApprovalPanel />

      <footer>
        Policy-enforced persistent memory control plane
      </footer>
    </main>
  );
}
