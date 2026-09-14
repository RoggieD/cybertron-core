import { useEffect, useRef } from "react";
import * as THREE from "three";

type GraphNode = {
  id: string;
  label: string;
  position: [number, number, number];
};

const NODES: GraphNode[] = [
  {
    id: "user",
    label: "USER",
    position: [-5, 0, 0],
  },
  {
    id: "router",
    label: "ROUTER",
    position: [-3, 0, 0],
  },
  {
    id: "agent",
    label: "AGENT",
    position: [-1, 0, 0],
  },
  {
    id: "memory",
    label: "MEMORY",
    position: [1, 1.6, 0],
  },
  {
    id: "tool",
    label: "TOOL",
    position: [1, -1.6, 0],
  },
  {
    id: "model",
    label: "MODEL",
    position: [4, 0, 0],
  },
];

const EDGES: Array<[string, string]> = [
  ["user", "router"],
  ["router", "agent"],
  ["agent", "memory"],
  ["agent", "tool"],
  ["memory", "model"],
  ["tool", "model"],
];

export default function CognitionGraph() {
  const mountRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const mount = mountRef.current;

    if (!mount) {
      return;
    }

    const scene = new THREE.Scene();

    const camera = new THREE.PerspectiveCamera(
      45,
      mount.clientWidth / mount.clientHeight,
      0.1,
      100,
    );

    camera.position.set(0, 0, 12);

    const renderer = new THREE.WebGLRenderer({
      antialias: true,
      alpha: true,
    });

    renderer.setPixelRatio(
      Math.min(window.devicePixelRatio, 2),
    );

    renderer.setSize(
      mount.clientWidth,
      mount.clientHeight,
    );

    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(
      0xffffff,
      1.2,
    );

    scene.add(ambient);

    const point = new THREE.PointLight(
      0xffffff,
      18,
    );

    point.position.set(0, 4, 8);
    scene.add(point);

    const nodeObjects = new Map<
      string,
      THREE.Mesh
    >();

    const nodeGeometry =
      new THREE.IcosahedronGeometry(
        0.38,
        2,
      );

    for (const node of NODES) {
      const material =
        new THREE.MeshStandardMaterial({
          emissive: 0x222222,
          emissiveIntensity: 1.3,
          roughness: 0.28,
          metalness: 0.55,
        });

      const mesh = new THREE.Mesh(
        nodeGeometry,
        material,
      );

      mesh.position.set(
        ...node.position,
      );

      scene.add(mesh);
      nodeObjects.set(node.id, mesh);
    }

    const edgeMaterial =
      new THREE.LineBasicMaterial({
        transparent: true,
        opacity: 0.45,
      });

    for (const [fromId, toId] of EDGES) {
      const from = nodeObjects.get(fromId);
      const to = nodeObjects.get(toId);

      if (!from || !to) {
        continue;
      }

      const geometry =
        new THREE.BufferGeometry().setFromPoints([
          from.position.clone(),
          to.position.clone(),
        ]);

      const line = new THREE.Line(
        geometry,
        edgeMaterial,
      );

      scene.add(line);
    }

    let frame = 0;

    function animate() {
      frame = requestAnimationFrame(
        animate,
      );

      const time =
        performance.now() * 0.001;

      for (const [
        index,
        mesh,
      ] of Array.from(
        nodeObjects.values(),
      ).entries()) {
        mesh.rotation.x =
          time * (0.12 + index * 0.015);

        mesh.rotation.y =
          time * (0.18 + index * 0.012);

        const pulse =
          1 +
          Math.sin(
            time * 1.8 + index,
          ) *
            0.035;

        mesh.scale.setScalar(pulse);
      }

      renderer.render(
        scene,
        camera,
      );
    }

    animate();

    function handleResize() {
      if (!mount) {
        return;
      }

      const width =
        mount.clientWidth;

      const height =
        mount.clientHeight;

      camera.aspect =
        width / height;

      camera.updateProjectionMatrix();

      renderer.setSize(
        width,
        height,
      );
    }

    window.addEventListener(
      "resize",
      handleResize,
    );

    return () => {
      window.removeEventListener(
        "resize",
        handleResize,
      );

      cancelAnimationFrame(frame);

      renderer.dispose();
      nodeGeometry.dispose();
      edgeMaterial.dispose();

      for (const mesh of nodeObjects.values()) {
        (
          mesh.material
          as THREE.Material
        ).dispose();
      }

      renderer.domElement.remove();
    };
  }, []);

  return (
    <section className="cognition-graph-panel">
      <div className="cognition-graph-header">
        <div>
          <div className="cognition-graph-kicker">
            LIVE COGNITION MAP
          </div>
          <h2>
            C.O.R.E. Processing Graph
          </h2>
        </div>
      </div>

      <div
        ref={mountRef}
        className="cognition-graph-canvas"
      />

      <div className="cognition-graph-legend">
        {NODES.map((node) => (
          <span key={node.id}>
            {node.label}
          </span>
        ))}
      </div>
    </section>
  );
}
