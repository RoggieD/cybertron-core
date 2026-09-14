import { lazy, Suspense } from "react";

const CognitionGraph = lazy(
  () => import("../components/CognitionGraph"),
);

export default function ProcessingPage() {
  return (
    <section className="core-processing-page">
      <div className="core-processing-heading">
        <span>LIVE ORCHESTRATION</span>
        <h1>Processing Graph</h1>
        <p>
          Real-time cognition flow across routing, agents, memory,
          tools, and the active model.
        </p>
      </div>

      <div className="core-processing-graph">
        <Suspense
          fallback={
            <div className="core-graph-loading">
              INITIALIZING COGNITION MAP…
            </div>
          }
        >
          <CognitionGraph />
        </Suspense>
      </div>
    </section>
  );
}
