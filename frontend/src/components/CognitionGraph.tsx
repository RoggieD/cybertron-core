import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import {
  connectCoreWebSocket,
  type CoreEvent,
} from "../api/websocket";

type NodeId =
  | "user"
  | "router"
  | "agent"
  | "memory"
  | "tool"
  | "model";

type GraphNode = {
  id: NodeId;
  label: string;
  position: [number, number, number];
};

type GraphEdge = {
  from: NodeId;
  to: NodeId;
};

const NODES: GraphNode[] = [
  { id: "user", label: "USER", position: [-5, 0, 0] },
  { id: "router", label: "ROUTER", position: [-3, 0, 0] },
  { id: "agent", label: "AGENT", position: [-1, 0, 0] },
  { id: "memory", label: "MEMORY", position: [1, 1.6, 0] },
  { id: "tool", label: "TOOL", position: [1, -1.6, 0] },
  { id: "model", label: "MODEL", position: [4, 0, 0] },
];

const EDGES: GraphEdge[] = [
  { from: "user", to: "router" },
  { from: "router", to: "agent" },
  { from: "agent", to: "memory" },
  { from: "agent", to: "tool" },
  { from: "memory", to: "model" },
  { from: "tool", to: "model" },
];

function eventNode(eventType: string): NodeId | null {
  if (eventType === "prompt.received") return "user";
  if (eventType.startsWith("router.")) return "router";
  if (eventType.startsWith("agent.")) return "agent";
  if (eventType.startsWith("memory.")) return "memory";
  if (eventType.startsWith("tool.")) return "tool";
  if (eventType.startsWith("model.")) return "model";
  if (eventType === "response.generated") return "user";
  return null;
}

export default function CognitionGraph() {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const activeNodeRef = useRef<NodeId | null>(null);
  const previousNodeRef = useRef<NodeId | null>(null);
  const [activeNode, setActiveNode] = useState<NodeId | null>(null);
  const [lastEvent, setLastEvent] = useState("WAITING");
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const socket = connectCoreWebSocket(
      (event: CoreEvent) => {
        const nextNode = eventNode(event.event_type);
        setLastEvent(event.event_type);

        if (nextNode) {
          previousNodeRef.current = activeNodeRef.current;
          activeNodeRef.current = nextNode;
          setActiveNode(nextNode);
        }
      },
      setConnected,
    );

    return () => socket.close();
  }, []);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(
      45,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100,
    );
    camera.position.set(0, 0, 12);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 1.1));
    const point = new THREE.PointLight(0xffffff, 22);
    point.position.set(0, 4, 8);
    scene.add(point);

    const nodeGeometry = new THREE.IcosahedronGeometry(0.42, 2);
    const nodeObjects = new Map<NodeId, THREE.Mesh>();

    for (const node of NODES) {
      const material = new THREE.MeshStandardMaterial({
        color: 0x9ca3af,
        emissive: 0x111827,
        emissiveIntensity: 0.7,
        roughness: 0.3,
        metalness: 0.65,
      });
      const mesh = new THREE.Mesh(nodeGeometry, material);
      mesh.position.set(...node.position);
      scene.add(mesh);
      nodeObjects.set(node.id, mesh);
    }

    const edgeObjects: Array<{
      edge: GraphEdge;
      line: THREE.Line;
      material: THREE.LineBasicMaterial;
    }> = [];

    for (const edge of EDGES) {
      const from = nodeObjects.get(edge.from);
      const to = nodeObjects.get(edge.to);
      if (!from || !to) continue;

      const geometry = new THREE.BufferGeometry().setFromPoints([
        from.position.clone(),
        to.position.clone(),
      ]);
      const material = new THREE.LineBasicMaterial({
        color: 0x64748b,
        transparent: true,
        opacity: 0.28,
      });
      const line = new THREE.Line(geometry, material);
      scene.add(line);
      edgeObjects.push({ edge, line, material });
    }

    let frame = 0;

    const animate = () => {
      frame = requestAnimationFrame(animate);
      const time = performance.now() * 0.001;
      const current = activeNodeRef.current;
      const previous = previousNodeRef.current;

      for (const [index, node] of NODES.entries()) {
        const mesh = nodeObjects.get(node.id);
        if (!mesh) continue;
        const material = mesh.material as THREE.MeshStandardMaterial;
        const isActive = node.id === current;

        mesh.rotation.x = time * (0.12 + index * 0.014);
        mesh.rotation.y = time * (0.18 + index * 0.012);
        const basePulse = 1 + Math.sin(time * 1.8 + index) * 0.035;
        const activePulse = isActive ? 1.18 + Math.sin(time * 6) * 0.08 : 1;
        mesh.scale.setScalar(basePulse * activePulse);

        material.color.setHex(isActive ? 0xe5e7eb : 0x9ca3af);
        material.emissive.setHex(isActive ? 0xffffff : 0x111827);
        material.emissiveIntensity = isActive ? 2.4 : 0.7;
      }

      for (const { edge, material } of edgeObjects) {
        const activePath =
          previous !== null &&
          current !== null &&
          edge.from === previous &&
          edge.to === current;

        material.color.setHex(activePath ? 0xffffff : 0x64748b);
        material.opacity = activePath
          ? 0.8 + Math.sin(time * 8) * 0.18
          : 0.28;
      }

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      const width = mount.clientWidth;
      const height = Math.max(mount.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height);
    };

    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(frame);
      renderer.dispose();
      nodeGeometry.dispose();

      for (const mesh of nodeObjects.values()) {
        (mesh.material as THREE.Material).dispose();
      }

      for (const { line, material } of edgeObjects) {
        line.geometry.dispose();
        material.dispose();
      }

      renderer.domElement.remove();
    };
  }, []);

  return (
    <section className="cognition-graph-panel">
      <div className="cognition-graph-header">
        <div>
          <div className="cognition-graph-kicker">LIVE COGNITION MAP</div>
          <h2>C.O.R.E. Processing Graph</h2>
        </div>
        <div className={`cognition-link-state ${connected ? "online" : "offline"}`}>
          {connected ? "EVENT BUS ONLINE" : "EVENT BUS OFFLINE"}
        </div>
      </div>

      <div className="cognition-graph-stage">
        <div ref={mountRef} className="cognition-graph-canvas" />
        <div className="cognition-node-labels" aria-hidden="true">
          {NODES.map((node) => (
            <span
              key={node.id}
              className={`cognition-node-label node-${node.id} ${
                activeNode === node.id ? "active" : ""
              }`}
            >
              {node.label}
            </span>
          ))}
        </div>
      </div>

      <div className="cognition-graph-footer">
        <span>ACTIVE: {activeNode?.toUpperCase() ?? "IDLE"}</span>
        <span>EVENT: {lastEvent}</span>
      </div>
    </section>
  );
}
