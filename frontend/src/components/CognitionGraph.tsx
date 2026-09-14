import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

import type { CoreEvent } from "../api/websocket";

type NodeId = string;
type SourceKind =
  | "policy"
  | "memory"
  | "historical"
  | "telemetry"
  | "external"
  | "generic";

type GraphNode = {
  id: NodeId;
  label: string;
  position: [number, number, number];
  provenance?: boolean;
  sourceKind?: SourceKind;
};

type GraphEdge = {
  from: NodeId;
  to: NodeId;
  provenance?: boolean;
  sourceKind?: SourceKind;
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

const SOURCE_COLORS: Record<SourceKind, number> = {
  policy: 0xc77dff,
  memory: 0xffd166,
  historical: 0xff7b00,
  telemetry: 0x00e5ff,
  external: 0xff4fd8,
  generic: 0xa8ff9e,
};

const BASE_NODE_COLORS: Record<string, number> = {
  user: 0x67e8ff,
  router: 0xa970ff,
  agent: 0xffd166,
  memory: 0xffa62b,
  tool: 0x2de2e6,
};

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is string => typeof item === "string" && !!item.trim(),
  );
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
  return trimmed.length > 22 ? `${trimmed.slice(0, 20)}…` : trimmed;
}

function classifySource(value: string, branch: "memory" | "tool"): SourceKind {
  const normalized = value.toLowerCase();

  if (normalized.includes("policy") || normalized.includes("auth")) {
    return "policy";
  }
  if (
    normalized.includes("incident") ||
    normalized.includes("history") ||
    normalized.includes("audit")
  ) {
    return "historical";
  }
  if (normalized.includes("memory") || normalized.includes("sqlite")) {
    return "memory";
  }
  if (
    normalized.includes("network") ||
    normalized.includes("docker") ||
    normalized.includes("system") ||
    normalized.includes("service") ||
    normalized.includes("process") ||
    normalized.includes("listener") ||
    normalized.includes("status")
  ) {
    return "telemetry";
  }
  if (
    normalized.includes("web") ||
    normalized.includes("github") ||
    normalized.includes("api") ||
    normalized.includes("intel") ||
    normalized.includes("external")
  ) {
    return "external";
  }

  return branch === "tool" ? "telemetry" : "generic";
}

function spreadPosition(
  index: number,
  count: number,
  y: number,
  z: number,
): [number, number, number] {
  const offset = index - (count - 1) / 2;
  return [1.6 + offset * 1.65, y + (index % 2 ? 0.18 : -0.06), z];
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
    const sourceKind = classifySource(source, "memory");
    nodes.push({
      id,
      label: normalizeLabel(source).toUpperCase(),
      position: spreadPosition(index, memorySources.length, 3.35, -0.45),
      provenance: true,
      sourceKind,
    });
    edges.push({
      from: id,
      to: "memory",
      provenance: true,
      sourceKind,
    });
  });

  tools.forEach((tool, index) => {
    const id = `tool-source:${tool}`;
    const sourceKind = classifySource(tool, "tool");
    nodes.push({
      id,
      label: normalizeLabel(tool).toUpperCase(),
      position: spreadPosition(index, tools.length, -3.35, 0.45),
      provenance: true,
      sourceKind,
    });
    edges.push({
      from: id,
      to: "tool",
      provenance: true,
      sourceKind,
    });
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
  if (eventType === "response.generated") return null;
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

function hexCss(value: number): string {
  return `#${value.toString(16).padStart(6, "0")}`;
}

function colorForNode(
  node: GraphNode,
  palette: ReturnType<typeof currentAccent>,
): number {
  if (node.provenance && node.sourceKind) {
    return SOURCE_COLORS[node.sourceKind];
  }
  if (node.id === "model") return palette.accent;
  return BASE_NODE_COLORS[node.id] ?? palette.idle;
}

function edgeColor(
  edge: GraphEdge,
  palette: ReturnType<typeof currentAccent>,
): number {
  if (edge.provenance && edge.sourceKind) {
    return SOURCE_COLORS[edge.sourceKind];
  }
  const destination = BASE_NODE_COLORS[edge.to];
  if (edge.to === "model") return palette.accent;
  return destination ?? palette.edge;
}

function createLabel(
  text: string,
  provenance: boolean,
  color: number,
) {
  const canvas = document.createElement("canvas");
  canvas.width = provenance ? 1536 : 1024;
  canvas.height = 256;

  const context = canvas.getContext("2d");
  if (!context) return null;

  const cssColor = hexCss(color);
  const fontSize = provenance ? 62 : 72;
  const paddingX = 42;
  const paddingY = 26;

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.font = `700 ${fontSize}px monospace`;
  context.textAlign = "center";
  context.textBaseline = "middle";

  const metrics = context.measureText(text);
  const panelWidth = Math.min(
    canvas.width - 24,
    Math.max(metrics.width + paddingX * 2, provenance ? 420 : 300),
  );
  const panelHeight = fontSize + paddingY * 2;
  const panelX = (canvas.width - panelWidth) / 2;
  const panelY = (canvas.height - panelHeight) / 2;

  context.fillStyle = "rgba(0, 5, 7, 0.86)";
  context.strokeStyle = cssColor;
  context.lineWidth = 5;
  context.beginPath();
  context.roundRect(panelX, panelY, panelWidth, panelHeight, 18);
  context.fill();
  context.stroke();

  context.shadowColor = "rgba(0, 0, 0, 0.95)";
  context.shadowBlur = 2;
  context.lineWidth = provenance ? 10 : 12;
  context.strokeStyle = "rgba(0, 0, 0, 0.96)";
  context.strokeText(text, canvas.width / 2, canvas.height / 2 + 2);

  context.shadowColor = cssColor;
  context.shadowBlur = 4;
  context.fillStyle = provenance ? "#ffffff" : cssColor;
  context.fillText(text, canvas.width / 2, canvas.height / 2 + 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.generateMipmaps = false;
  texture.minFilter = THREE.LinearFilter;
  texture.magFilter = THREE.LinearFilter;
  texture.needsUpdate = true;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
    depthTest: false,
  });

  const sprite = new THREE.Sprite(material);
  sprite.scale.set(provenance ? 4.4 : 3.25, provenance ? 0.74 : 0.8, 1);
  sprite.renderOrder = 20;

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
  const [observedProvenance, setObservedProvenance] =
    useState<CognitionProvenance>(EMPTY_PROVENANCE);

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
          memorySources: Array.from(
            new Set([...current.memorySources, ...sources]),
          ),
        }));
      }
    }

    if (event.event_type.startsWith("tool.")) {
      const tool = entityId(event, "tool");
      if (tool) {
        setObservedProvenance((current) => ({
          ...current,
          tools: current.tools.includes(tool)
            ? current.tools
            : [...current.tools, tool],
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
    scene.fog = new THREE.FogExp2(0x020507, 0.047);

    const camera = new THREE.PerspectiveCamera(
      43,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100,
    );
    camera.position.set(0, 0.05, 11.4);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
      powerPreference: "high-performance",
    });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.32;
    mount.replaceChildren(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.58));

    const keyLight = new THREE.PointLight(palette.accent, 36, 30);
    keyLight.position.set(0, 3.5, 7);
    scene.add(keyLight);

    const violetLight = new THREE.PointLight(0xa970ff, 15, 18);
    violetLight.position.set(-3.2, 2.2, 4.5);
    scene.add(violetLight);

    const cyanLight = new THREE.PointLight(0x00e5ff, 13, 18);
    cyanLight.position.set(2.2, -2.5, 4.2);
    scene.add(cyanLight);

    const amberLight = new THREE.PointLight(0xffa62b, 11, 16);
    amberLight.position.set(1.8, 3.1, 3.5);
    scene.add(amberLight);

    const starGeometry = new THREE.BufferGeometry();
    const starPositions = new Float32Array(270 * 3);
    for (let i = 0; i < starPositions.length; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 25;
      starPositions[i + 1] = (Math.random() - 0.5) * 15;
      starPositions[i + 2] = -2 - Math.random() * 8;
    }
    starGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(starPositions, 3),
    );
    const starMaterial = new THREE.PointsMaterial({
      color: palette.accent,
      size: 0.026,
      transparent: true,
      opacity: 0.36,
      depthWrite: false,
    });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);

    const nodeGeometry = new THREE.IcosahedronGeometry(0.5, 3);
    const sourceGeometry = new THREE.OctahedronGeometry(0.29, 2);
    const haloGeometry = new THREE.RingGeometry(0.68, 0.73, 64);
    const sourceHaloGeometry = new THREE.RingGeometry(0.4, 0.44, 48);
    const nodeObjects = new Map<NodeId, THREE.Mesh>();
    const haloObjects = new Map<NodeId, THREE.Mesh>();
    const labels: Array<{
      material: THREE.SpriteMaterial;
      texture: THREE.Texture;
    }> = [];

    for (const node of graph.nodes) {
      const nodeColor = colorForNode(node, palette);
      const material = new THREE.MeshStandardMaterial({
        color: nodeColor,
        emissive: nodeColor,
        emissiveIntensity: node.provenance ? 1.7 : 1.1,
        roughness: 0.18,
        metalness: 0.74,
      });
      const mesh = new THREE.Mesh(
        node.provenance ? sourceGeometry : nodeGeometry,
        material,
      );
      mesh.position.set(...node.position);
      scene.add(mesh);
      nodeObjects.set(node.id, mesh);

      const haloMaterial = new THREE.MeshBasicMaterial({
        color: nodeColor,
        transparent: true,
        opacity: node.provenance ? 0.38 : 0.2,
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

      const label = createLabel(node.label, !!node.provenance, nodeColor);
      if (label) {
        label.sprite.position.copy(mesh.position);
        label.sprite.position.y -= node.provenance ? 0.78 : 1.02;
        scene.add(label.sprite);
        labels.push({ material: label.material, texture: label.texture });
      }
    }

    const edgeObjects: Array<{
      edge: GraphEdge;
      line: THREE.Line;
      material: THREE.LineBasicMaterial;
      baseColor: number;
    }> = [];

    for (const edge of graph.edges) {
      const from = nodeObjects.get(edge.from);
      const to = nodeObjects.get(edge.to);
      if (!from || !to) continue;

      const geometry = new THREE.BufferGeometry().setFromPoints([
        from.position.clone(),
        to.position.clone(),
      ]);
      const baseColor = edgeColor(edge, palette);
      const material = new THREE.LineBasicMaterial({
        color: baseColor,
        transparent: true,
        opacity: edge.provenance ? 0.8 : 0.52,
      });
      const line = new THREE.Line(geometry, material);
      scene.add(line);
      edgeObjects.push({ edge, line, material, baseColor });
    }

    const packetGeometry = new THREE.SphereGeometry(0.11, 20, 20);
    const packetMaterial = new THREE.MeshBasicMaterial({
      color: 0xffffff,
      transparent: true,
      opacity: 0,
    });
    const packet = new THREE.Mesh(packetGeometry, packetMaterial);
    scene.add(packet);

    const packetLight = new THREE.PointLight(palette.accent, 12, 3.4);
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
        const nodeColor = colorForNode(node, palette);

        mesh.rotation.x = time * (0.16 + index * 0.015);
        mesh.rotation.y = time * (0.22 + index * 0.012);

        const idlePulse = 1 + Math.sin(time * 1.5 + index) * 0.025;
        const sourcePulse = node.provenance
          ? 1.05 + Math.sin(time * 3 + index) * 0.06
          : 1;
        const activePulse = isActive
          ? 1.16 + Math.sin(time * 7) * 0.07
          : 1;
        mesh.scale.setScalar(idlePulse * sourcePulse * activePulse);

        material.color.setHex(isActive ? 0xffffff : nodeColor);
        material.emissive.setHex(nodeColor);
        material.emissiveIntensity = isActive
          ? 4.8
          : node.provenance
            ? 2.0 + Math.sin(time * 3 + index) * 0.4
            : 1.25;

        haloMaterial.color.setHex(nodeColor);
        halo.scale.setScalar(
          isActive
            ? 1.24 + Math.sin(time * 5) * 0.1
            : node.provenance
              ? sourcePulse
              : 1,
        );
        haloMaterial.opacity = isActive
          ? 0.86 + Math.sin(time * 6) * 0.1
          : node.provenance
            ? 0.42 + Math.sin(time * 3 + index) * 0.13
            : 0.18;
      }

      for (const { edge, material, baseColor } of edgeObjects) {
        const activePath =
          previous !== null &&
          current !== null &&
          ((edge.from === previous && edge.to === current) ||
            (edge.from === current && edge.to === previous));

        material.color.setHex(activePath ? 0xffffff : baseColor);
        material.opacity = activePath
          ? 0.96
          : edge.provenance
            ? 0.72 + Math.sin(time * 4) * 0.16
            : 0.5;
      }

      const previousMesh = previous ? nodeObjects.get(previous) : null;
      const currentMesh = current ? nodeObjects.get(current) : null;

      if (previousMesh && currentMesh && previous !== current) {
        const elapsed = now - transitionStartedRef.current;
        const duration = 650;
        const progress = Math.min(elapsed / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);

        packet.position.lerpVectors(
          previousMesh.position,
          currentMesh.position,
          eased,
        );
        packetMaterial.opacity = progress < 1 ? 0.98 : 0;
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

  const legendItems: Array<[string, number]> = [
    ["USER", BASE_NODE_COLORS.user],
    ["ROUTER", BASE_NODE_COLORS.router],
    ["AGENT", BASE_NODE_COLORS.agent],
    ["MEMORY", BASE_NODE_COLORS.memory],
    ["TOOL", BASE_NODE_COLORS.tool],
    ["MODEL", currentAccent().accent],
  ];

  return (
    <section className="cognition-graph-panel">
      <div className="cognition-graph-header">
        <div>
          <div className="cognition-graph-kicker">
            LIVE COGNITION + EVIDENCE TOPOLOGY
          </div>
          <h2>C.O.R.E. Processing Graph</h2>
        </div>
        <div className={`cognition-link-state ${connected ? "online" : "offline"}`}>
          {connected ? "EVENT BUS ONLINE" : "EVENT BUS OFFLINE"}
        </div>
      </div>

      <div
        ref={mountRef}
        className="cognition-graph-canvas"
        style={{ height: "560px" }}
      />

      <div className="cognition-graph-legend">
        {legendItems.map(([label, color]) => (
          <span key={label} style={{ color: hexCss(color), borderColor: hexCss(color) }}>
            {label}{activeNode === label.toLowerCase() ? " • ACTIVE" : ""}
          </span>
        ))}
        <span style={{ color: hexCss(SOURCE_COLORS.policy), borderColor: hexCss(SOURCE_COLORS.policy) }}>
          POLICY
        </span>
        <span style={{ color: hexCss(SOURCE_COLORS.historical), borderColor: hexCss(SOURCE_COLORS.historical) }}>
          HISTORY
        </span>
        <span style={{ color: hexCss(SOURCE_COLORS.telemetry), borderColor: hexCss(SOURCE_COLORS.telemetry) }}>
          LIVE DATA
        </span>
        <span style={{ color: hexCss(SOURCE_COLORS.external), borderColor: hexCss(SOURCE_COLORS.external) }}>
          EXTERNAL INTEL
        </span>
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
