import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { CoreEvent } from "../api/websocket";

type NodeId = string;

type GraphNode = {
  id: NodeId;
  label: string;
  position: [number, number, number];
  provenance?: boolean;
};

type GraphEdge = {
  from: NodeId;
  to: NodeId;
  provenance?: boolean;
};

export type CognitionProvenance = {
  memorySources: string[];
  tools: string[];
};

const EMPTY_PROVENANCE: CognitionProvenance = {
  memorySources: [],
  tools: [],
};

const BASE_NODES: GraphNode[] = [
  { id: "user", label: "USER", position: [-5.1, 0, 0] },
  { id: "router", label: "ROUTER", position: [-3.1, 0, 0.15] },
  { id: "agent", label: "AGENT", position: [-1.0, 0, 0.3] },
  { id: "memory", label: "MEMORY", position: [1.15, 1.45, -0.2] },
  { id: "tool", label: "TOOL", position: [1.15, -1.45, 0.2] },
  { id: "model", label: "MODEL", position: [4.9, 0, 0] },
];

const BASE_EDGES: GraphEdge[] = [
  { from: "user", to: "router" },
  { from: "router", to: "agent" },
  { from: "agent", to: "memory" },
  { from: "agent", to: "tool" },
  { from: "memory", to: "model" },
  { from: "tool", to: "model" },
  { from: "model", to: "user" },
];

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => typeof item === "string" && !!item.trim());
}

function entityId(event: CoreEvent, type: string): string | null {
  if (event.target?.type === type && typeof event.target.id === "string") {
    return event.target.id;
  }
  if (event.actor?.type === type && typeof event.actor.id === "string") {
    return event.actor.id;
  }
  return null;
}

function normalizeLabel(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return "UNKNOWN";
  return trimmed.length > 18 ? `${trimmed.slice(0, 16)}…` : trimmed;
}

function buildGraph(provenance: CognitionProvenance): {
  nodes: GraphNode[];
  edges: GraphEdge[];
} {
  const nodes = [...BASE_NODES];
  const edges = [...BASE_EDGES];

  const memorySources = provenance.memorySources.slice(0, 4);
  const tools = provenance.tools.slice(0, 4);

  memorySources.forEach((source, index) => {
    const id = `memory-source:${source}`;
    const offset = index - (memorySources.length - 1) / 2;
    nodes.push({
      id,
      label: normalizeLabel(source).toUpperCase(),
      position: [2.7 + Math.abs(offset) * 0.15, 2.85 + offset * 0.65, -0.45],
      provenance: true,
    });
    edges.push({ from: id, to: "memory", provenance: true });
  });

  tools.forEach((tool, index) => {
    const id = `tool-source:${tool}`;
    const offset = index - (tools.length - 1) / 2;
    nodes.push({
      id,
      label: normalizeLabel(tool).toUpperCase(),
      position: [2.7 + Math.abs(offset) * 0.15, -2.85 + offset * 0.65, 0.45],
      provenance: true,
    });
    edges.push({ from: id, to: "tool", provenance: true });
  });

  return { nodes, edges };
}

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

function currentAccent() {
  const green = document.documentElement.dataset.coreTheme === "neon-green";
  return green
    ? {
        accent: 0x39ff14,
        accentSoft: 0xaaff98,
        idle: 0x315d2f,
        idleEmissive: 0x0b3510,
        edge: 0x2e6827,
        text: "#e6ffe1",
        shadow: "#39ff14",
      }
    : {
        accent: 0x53e6ff,
        accentSoft: 0xa7f6ff,
        idle: 0x315d68,
        idleEmissive: 0x062d35,
        edge: 0x245968,
        text: "#d9fbff",
        shadow: "#53e6ff",
      };
}

function createLabel(
  text: string,
  provenance: boolean,
  palette: ReturnType<typeof currentAccent>,
) {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 96;

  const context = canvas.getContext("2d");
  if (!context) return null;

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.font = provenance ? "500 24px monospace" : "600 34px monospace";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.shadowColor = palette.shadow;
  context.shadowBlur = provenance ? 7 : 12;
  context.fillStyle = palette.text;
  context.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(material);
  sprite.scale.set(provenance ? 2.55 : 2.3, provenance ? 0.48 : 0.58, 1);

  return { sprite, material, texture };
}

export default function CognitionGraph({
  event,
  connected,
  provenance,
}: {
  event: CoreEvent | null;
  connected: boolean;
  provenance?: CognitionProvenance;
}) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const activeNodeRef = useRef<NodeId | null>(null);
  const previousNodeRef = useRef<NodeId | null>(null);
  const transitionStartedRef = useRef(0);
  const [activeNode, setActiveNode] = useState<NodeId | null>(null);
  const [lastEvent, setLastEvent] = useState("WAITING");
  const [observedProvenance, setObservedProvenance] = useState<CognitionProvenance>(EMPTY_PROVENANCE);

  useEffect(() => {
    if (!event) return;

    const nextNode = eventNode(event.event_type);
    setLastEvent(event.event_type);

    if (event.event_type === "prompt.received") {
      setObservedProvenance(EMPTY_PROVENANCE);
    }

    if (event.event_type === "memory.search_completed") {
      const sources = stringList(event.metadata?.sources);
      if (sources.length) {
        setObservedProvenance((current) => ({
          ...current,
          memorySources: Array.from(new Set([...current.memorySources, ...sources])),
        }));
      }
    }

    if (event.event_type.startsWith("tool.")) {
      const tool = entityId(event, "tool");
      if (tool) {
        setObservedProvenance((current) => ({
          ...current,
          tools: current.tools.includes(tool) ? current.tools : [...current.tools, tool],
        }));
      }
    }

    if (nextNode) {
      previousNodeRef.current = activeNodeRef.current;
      activeNodeRef.current = nextNode;
      transitionStartedRef.current = performance.now();
      setActiveNode(nextNode);
    }
  }, [event]);

  const effectiveProvenance = provenance ?? observedProvenance;

  const graph = useMemo(
    () => buildGraph(effectiveProvenance),
    [effectiveProvenance.memorySources, effectiveProvenance.tools],
  );

  const graphSignature = useMemo(
    () => graph.nodes.map((node) => node.id).join("|"),
    [graph],
  );

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const palette = currentAccent();
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x020507, 0.05);

    const camera = new THREE.PerspectiveCamera(
      43,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100,
    );
    camera.position.set(0, 0.1, 11.7);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    mount.replaceChildren(renderer.domElement);

    scene.add(new THREE.AmbientLight(palette.accentSoft, 0.7));

    const keyLight = new THREE.PointLight(palette.accent, 42, 30);
    keyLight.position.set(0, 3.5, 7);
    scene.add(keyLight);

    const rimLight = new THREE.PointLight(0x3a7cff, 22, 24);
    rimLight.position.set(-5, -3, 4);
    scene.add(rimLight);

    const starGeometry = new THREE.BufferGeometry();
    const starPositions = new Float32Array(240 * 3);
    for (let i = 0; i < starPositions.length; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 24;
      starPositions[i + 1] = (Math.random() - 0.5) * 14;
      starPositions[i + 2] = -2 - Math.random() * 8;
    }
    starGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(starPositions, 3),
    );
    const starMaterial = new THREE.PointsMaterial({
      color: palette.accent,
      size: 0.025,
      transparent: true,
      opacity: 0.34,
      depthWrite: false,
    });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);

    const nodeGeometry = new THREE.IcosahedronGeometry(0.5, 3);
    const sourceGeometry = new THREE.OctahedronGeometry(0.28, 2);
    const haloGeometry = new THREE.RingGeometry(0.68, 0.73, 64);
    const sourceHaloGeometry = new THREE.RingGeometry(0.4, 0.43, 48);
    const nodeObjects = new Map<NodeId, THREE.Mesh>();
    const haloObjects = new Map<NodeId, THREE.Mesh>();
    const labels: Array<{
      material: THREE.SpriteMaterial;
      texture: THREE.Texture;
    }> = [];

    for (const node of graph.nodes) {
      const material = new THREE.MeshStandardMaterial({
        color: node.provenance ? palette.edge : palette.idle,
        emissive: palette.idleEmissive,
        emissiveIntensity: node.provenance ? 1.9 : 1.4,
        roughness: 0.2,
        metalness: 0.72,
      });
      const mesh = new THREE.Mesh(node.provenance ? sourceGeometry : nodeGeometry, material);
      mesh.position.set(...node.position);
      scene.add(mesh);
      nodeObjects.set(node.id, mesh);

      const haloMaterial = new THREE.MeshBasicMaterial({
        color: palette.accent,
        transparent: true,
        opacity: node.provenance ? 0.28 : 0.16,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const halo = new THREE.Mesh(
        node.provenance ? sourceHaloGeometry : haloGeometry,
        haloMaterial,
      );
      halo.position.copy(mesh.position);
      scene.add(halo);
      haloObjects.set(node.id, halo);

      const label = createLabel(node.label, !!node.provenance, palette);
      if (label) {
        label.sprite.position.copy(mesh.position);
        label.sprite.position.y -= node.provenance ? 0.57 : 0.9;
        scene.add(label.sprite);
        labels.push({ material: label.material, texture: label.texture });
      }
    }

    const edgeObjects: Array<{
      edge: GraphEdge;
      line: THREE.Line;
      material: THREE.LineBasicMaterial;
    }> = [];

    for (const edge of graph.edges) {
      const from = nodeObjects.get(edge.from);
      const to = nodeObjects.get(edge.to);
      if (!from || !to) continue;

      const geometry = new THREE.BufferGeometry().setFromPoints([
        from.position.clone(),
        to.position.clone(),
      ]);
      const material = new THREE.LineBasicMaterial({
        color: palette.edge,
        transparent: true,
        opacity: edge.provenance ? 0.72 : 0.48,
      });
      const line = new THREE.Line(geometry, material);
      scene.add(line);
      edgeObjects.push({ edge, line, material });
    }

    const packetGeometry = new THREE.SphereGeometry(0.11, 20, 20);
    const packetMaterial = new THREE.MeshBasicMaterial({
      color: palette.accentSoft,
      transparent: true,
      opacity: 0,
    });
    const packet = new THREE.Mesh(packetGeometry, packetMaterial);
    scene.add(packet);

    const packetLight = new THREE.PointLight(palette.accent, 10, 3.2);
    packet.add(packetLight);

    let frame = 0;

    const animate = () => {
      frame = requestAnimationFrame(animate);
      const now = performance.now();
      const time = now * 0.001;
      const current = activeNodeRef.current;
      const previous = previousNodeRef.current;

      stars.rotation.z = time * 0.006;

      for (const [index, node] of graph.nodes.entries()) {
        const mesh = nodeObjects.get(node.id);
        const halo = haloObjects.get(node.id);
        if (!mesh || !halo) continue;

        const material = mesh.material as THREE.MeshStandardMaterial;
        const haloMaterial = halo.material as THREE.MeshBasicMaterial;
        const isActive = node.id === current;

        mesh.rotation.x = time * (0.16 + index * 0.015);
        mesh.rotation.y = time * (0.22 + index * 0.012);

        const idlePulse = 1 + Math.sin(time * 1.5 + index) * 0.025;
        const sourcePulse = node.provenance ? 1.05 + Math.sin(time * 3 + index) * 0.06 : 1;
        const activePulse = isActive ? 1.16 + Math.sin(time * 7) * 0.07 : 1;
        mesh.scale.setScalar(idlePulse * sourcePulse * activePulse);

        if (isActive) {
          material.color.setHex(palette.accentSoft);
          material.emissive.setHex(palette.accent);
          material.emissiveIntensity = 4.2;
        } else if (node.provenance) {
          material.color.setHex(palette.edge);
          material.emissive.setHex(palette.accent);
          material.emissiveIntensity = 1.7 + Math.sin(time * 3 + index) * 0.35;
        } else {
          material.color.setHex(palette.idle);
          material.emissive.setHex(palette.idleEmissive);
          material.emissiveIntensity = 1.4;
        }

        halo.scale.setScalar(
          isActive ? 1.22 + Math.sin(time * 5) * 0.1 : node.provenance ? sourcePulse : 1,
        );
        haloMaterial.opacity = isActive
          ? 0.72 + Math.sin(time * 6) * 0.2
          : node.provenance
            ? 0.34 + Math.sin(time * 3 + index) * 0.12
            : 0.12;
      }

      for (const { edge, material } of edgeObjects) {
        const activePath =
          previous !== null &&
          current !== null &&
          ((edge.from === previous && edge.to === current) ||
            (edge.from === current && edge.to === previous));

        material.color.setHex(activePath ? palette.accentSoft : palette.edge);
        material.opacity = activePath
          ? 0.82 + Math.sin(time * 9) * 0.16
          : edge.provenance
            ? 0.66 + Math.sin(time * 4) * 0.12
            : 0.48;
      }

      const previousMesh = previous ? nodeObjects.get(previous) : null;
      const currentMesh = current ? nodeObjects.get(current) : null;

      if (previousMesh && currentMesh && previous !== current) {
        const elapsed = now - transitionStartedRef.current;
        const duration = 650;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);

        packet.position.lerpVectors(previousMesh.position, currentMesh.position, eased);
        packetMaterial.opacity = progress < 1 ? 0.95 : 0;
        packet.scale.setScalar(1 + Math.sin(time * 18) * 0.2);
      } else {
        packetMaterial.opacity = 0;
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
      sourceGeometry.dispose();
      haloGeometry.dispose();
      sourceHaloGeometry.dispose();
      starGeometry.dispose();
      starMaterial.dispose();
      packetGeometry.dispose();
      packetMaterial.dispose();

      for (const mesh of nodeObjects.values()) {
        (mesh.material as THREE.Material).dispose();
      }
      for (const halo of haloObjects.values()) {
        (halo.material as THREE.Material).dispose();
      }
      for (const { line, material } of edgeObjects) {
        line.geometry.dispose();
        material.dispose();
      }
      for (const label of labels) {
        label.material.dispose();
        label.texture.dispose();
      }

      renderer.domElement.remove();
    };
  }, [graphSignature]);

  const provenanceCount =
    effectiveProvenance.memorySources.length + effectiveProvenance.tools.length;

  return (
    <section className="cognition-graph-panel">
      <div className="cognition-graph-header">
        <div>
          <div className="cognition-graph-kicker">LIVE COGNITION + PROVENANCE MAP</div>
          <h2>C.O.R.E. Processing Graph</h2>
        </div>
        <div className={`cognition-link-state ${connected ? "online" : "offline"}`}>
          {connected ? "EVENT BUS ONLINE" : "EVENT BUS OFFLINE"}
        </div>
      </div>

      <div ref={mountRef} className="cognition-graph-canvas" />

      <div className="cognition-graph-legend">
        {BASE_NODES.map((node) => (
          <span key={node.id}>
            {node.label}{activeNode === node.id ? " • ACTIVE" : ""}
          </span>
        ))}
        <span>PROVENANCE SOURCES: {provenanceCount}</span>
      </div>

      <div className="cognition-graph-footer">
        <span>ACTIVE: {activeNode?.toUpperCase() ?? "IDLE"}</span>
        <span>SOURCES: {provenanceCount}</span>
        <span>EVENT: {lastEvent}</span>
      </div>
    </section>
  );
}
