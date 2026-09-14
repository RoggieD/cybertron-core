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
  { id: "user", label: "USER", position: [-4.7, 0, 0] },
  { id: "router", label: "ROUTER", position: [-2.8, 0, 0.15] },
  { id: "agent", label: "AGENT", position: [-0.8, 0, 0.3] },
  { id: "memory", label: "MEMORY", position: [1.2, 1.65, -0.2] },
  { id: "tool", label: "TOOL", position: [1.2, -1.65, 0.2] },
  { id: "model", label: "MODEL", position: [4.1, 0, 0] },
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

function createLabel(text: string) {
  const canvas = document.createElement("canvas");
  canvas.width = 384;
  canvas.height = 96;

  const context = canvas.getContext("2d");
  if (!context) return null;

  context.clearRect(0, 0, canvas.width, canvas.height);
  context.font = "600 34px monospace";
  context.textAlign = "center";
  context.textBaseline = "middle";
  context.shadowColor = "#53e6ff";
  context.shadowBlur = 12;
  context.fillStyle = "#d9fbff";
  context.fillText(text, canvas.width / 2, canvas.height / 2);

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;

  const material = new THREE.SpriteMaterial({
    map: texture,
    transparent: true,
    depthWrite: false,
  });

  const sprite = new THREE.Sprite(material);
  sprite.scale.set(2.3, 0.58, 1);

  return { sprite, material, texture };
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
    scene.fog = new THREE.FogExp2(0x020507, 0.055);

    const camera = new THREE.PerspectiveCamera(
      43,
      mount.clientWidth / Math.max(mount.clientHeight, 1),
      0.1,
      100,
    );
    camera.position.set(0, 0.1, 10.5);

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
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0x8befff, 0.7));

    const keyLight = new THREE.PointLight(0x53e6ff, 42, 28);
    keyLight.position.set(0, 3.5, 7);
    scene.add(keyLight);

    const rimLight = new THREE.PointLight(0x3a7cff, 28, 24);
    rimLight.position.set(-5, -3, 4);
    scene.add(rimLight);

    const starGeometry = new THREE.BufferGeometry();
    const starPositions = new Float32Array(240 * 3);
    for (let i = 0; i < starPositions.length; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 22;
      starPositions[i + 1] = (Math.random() - 0.5) * 12;
      starPositions[i + 2] = -2 - Math.random() * 8;
    }
    starGeometry.setAttribute(
      "position",
      new THREE.BufferAttribute(starPositions, 3),
    );
    const starMaterial = new THREE.PointsMaterial({
      color: 0x53e6ff,
      size: 0.025,
      transparent: true,
      opacity: 0.38,
      depthWrite: false,
    });
    const stars = new THREE.Points(starGeometry, starMaterial);
    scene.add(stars);

    const nodeGeometry = new THREE.IcosahedronGeometry(0.5, 3);
    const haloGeometry = new THREE.RingGeometry(0.68, 0.73, 64);
    const nodeObjects = new Map<NodeId, THREE.Mesh>();
    const haloObjects = new Map<NodeId, THREE.Mesh>();
    const labels: Array<{
      material: THREE.SpriteMaterial;
      texture: THREE.Texture;
    }> = [];

    for (const node of NODES) {
      const material = new THREE.MeshStandardMaterial({
        color: 0x315d68,
        emissive: 0x062d35,
        emissiveIntensity: 1.4,
        roughness: 0.2,
        metalness: 0.72,
      });
      const mesh = new THREE.Mesh(nodeGeometry, material);
      mesh.position.set(...node.position);
      scene.add(mesh);
      nodeObjects.set(node.id, mesh);

      const haloMaterial = new THREE.MeshBasicMaterial({
        color: 0x53e6ff,
        transparent: true,
        opacity: 0.16,
        side: THREE.DoubleSide,
        depthWrite: false,
      });
      const halo = new THREE.Mesh(haloGeometry, haloMaterial);
      halo.position.copy(mesh.position);
      scene.add(halo);
      haloObjects.set(node.id, halo);

      const label = createLabel(node.label);
      if (label) {
        label.sprite.position.copy(mesh.position);
        label.sprite.position.y -= 0.9;
        scene.add(label.sprite);
        labels.push({
          material: label.material,
          texture: label.texture,
        });
      }
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
        color: 0x245968,
        transparent: true,
        opacity: 0.48,
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

      stars.rotation.z = time * 0.006;

      for (const [index, node] of NODES.entries()) {
        const mesh = nodeObjects.get(node.id);
        const halo = haloObjects.get(node.id);
        if (!mesh || !halo) continue;

        const material = mesh.material as THREE.MeshStandardMaterial;
        const haloMaterial = halo.material as THREE.MeshBasicMaterial;
        const isActive = node.id === current;

        mesh.rotation.x = time * (0.16 + index * 0.015);
        mesh.rotation.y = time * (0.22 + index * 0.012);

        const idlePulse = 1 + Math.sin(time * 1.5 + index) * 0.025;
        const activePulse = isActive ? 1.16 + Math.sin(time * 7) * 0.07 : 1;
        mesh.scale.setScalar(idlePulse * activePulse);

        material.color.setHex(isActive ? 0xa7f6ff : 0x315d68);
        material.emissive.setHex(isActive ? 0x32dff5 : 0x062d35);
        material.emissiveIntensity = isActive ? 4.2 : 1.4;

        halo.scale.setScalar(
          isActive ? 1.22 + Math.sin(time * 5) * 0.1 : 1,
        );
        haloMaterial.opacity = isActive
          ? 0.72 + Math.sin(time * 6) * 0.2
          : 0.12;
      }

      for (const { edge, material } of edgeObjects) {
        const activePath =
          previous !== null &&
          current !== null &&
          edge.from === previous &&
          edge.to === current;

        material.color.setHex(activePath ? 0x8ff5ff : 0x245968);
        material.opacity = activePath
          ? 0.82 + Math.sin(time * 9) * 0.16
          : 0.48;
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
      haloGeometry.dispose();
      starGeometry.dispose();
      starMaterial.dispose();

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

      <div ref={mountRef} className="cognition-graph-canvas" />

      <div className="cognition-graph-legend">
        {NODES.map((node) => (
          <span key={node.id}>
            {node.label}{activeNode === node.id ? " • ACTIVE" : ""}
          </span>
        ))}
      </div>

      <div className="cognition-graph-footer">
        <span>ACTIVE: {activeNode?.toUpperCase() ?? "IDLE"}</span>
        <span>EVENT: {lastEvent}</span>
      </div>
    </section>
  );
}
