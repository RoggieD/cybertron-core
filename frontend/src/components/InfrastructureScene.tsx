import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import type { InfrastructureNode, InfrastructureSnapshot } from "../api/infrastructure";

const COLORS = {host: 0x53e6ff, engine: 0xb58aff, container: 0x39ff94, service: 0xffce73};

export default function InfrastructureScene({nodes, edges, selected, onSelect}: {
  nodes: InfrastructureNode[]; edges: InfrastructureSnapshot["edges"];
  selected: string | null; onSelect: (id: string) => void;
}) {
  const mount = useRef<HTMLDivElement>(null);
  const selection = useRef(selected);
  const choose = useRef(onSelect);
  const [unavailable, setUnavailable] = useState(false);
  useEffect(() => { selection.current = selected; }, [selected]);
  useEffect(() => { choose.current = onSelect; }, [onSelect]);

  useEffect(() => {
    const element = mount.current;
    if (!element) return;
    let renderer: THREE.WebGLRenderer;
    try { renderer = new THREE.WebGLRenderer({antialias: true, alpha: true}); }
    catch { setUnavailable(true); return; }
    setUnavailable(false);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    element.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(48, 1, .1, 300);
    camera.position.set(0, 5, 24);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.minDistance = 3; controls.maxDistance = 100;
    const geometry = new THREE.IcosahedronGeometry(.3, 1);
    const meshes: THREE.Mesh[] = [];
    const positions = new Map<string, THREE.Vector3>();
    const materials: THREE.Material[] = [];
    const textures: THREE.Texture[] = [];
    const kinds = ["host", "engine", "container", "service"];
    for (const kind of kinds) {
      const group = nodes.filter(n => n.kind === kind);
      group.forEach((node, index) => {
        const angle = index * Math.PI * 2 / Math.max(1, group.length) + kinds.indexOf(kind) * 1.05;
        const radius = kind === "host" ? 0 : kind === "engine" ? 2.5 : kind === "container" ? 6 : 10;
        const pos = new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius * .6, (index % 3 - 1) * 1.3);
        positions.set(node.id, pos);
        const material = new THREE.MeshBasicMaterial({color: node.state === "check failed" || node.state === "exited" ? 0xff6978 : COLORS[node.kind]});
        materials.push(material);
        const mesh = new THREE.Mesh(geometry, material);
        mesh.position.copy(pos); mesh.userData.id = node.id;
        meshes.push(mesh); scene.add(mesh);
        // Bound text overhead; every entity remains searchable in the accessible list.
        if (index < 40) {
          const canvas = document.createElement("canvas"); canvas.width = 320; canvas.height = 64;
          const context = canvas.getContext("2d")!;
          context.fillStyle = "#031017"; context.fillRect(0, 0, 320, 64);
          context.font = "24px sans-serif"; context.fillStyle = "#e5fbff"; context.textAlign = "center";
          context.fillText(node.label.length > 22 ? `${node.label.slice(0, 19)}…` : node.label, 160, 40);
          const texture = new THREE.CanvasTexture(canvas); textures.push(texture);
          const labelMaterial = new THREE.SpriteMaterial({map: texture, depthTest: false}); materials.push(labelMaterial);
          const label = new THREE.Sprite(labelMaterial); label.position.copy(pos); label.position.y -= .85; label.scale.set(5, 1, 1); scene.add(label);
        }
      });
    }
    const points: THREE.Vector3[] = [];
    edges.forEach(edge => { const a = positions.get(edge.source), b = positions.get(edge.target); if(a && b) points.push(a, b); });
    const lineGeometry = new THREE.BufferGeometry().setFromPoints(points);
    const lineMaterial = new THREE.LineBasicMaterial({color: 0x56878b, transparent: true, opacity: .45});
    scene.add(new THREE.LineSegments(lineGeometry, lineMaterial));
    const raycaster = new THREE.Raycaster();
    let down = [0, 0];
    const start = (event: PointerEvent) => { down = [event.clientX, event.clientY]; };
    const click = (event: PointerEvent) => {
      if (Math.hypot(event.clientX - down[0], event.clientY - down[1]) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      raycaster.setFromCamera(new THREE.Vector2((event.clientX-rect.left)/rect.width*2-1, -(event.clientY-rect.top)/rect.height*2+1), camera);
      const hit = raycaster.intersectObjects(meshes)[0];
      if(hit) choose.current(hit.object.userData.id);
    };
    renderer.domElement.addEventListener("pointerdown", start);
    renderer.domElement.addEventListener("pointerup", click);
    const resize = new ResizeObserver(() => {
      const width = element.clientWidth, height = element.clientHeight;
      if (!width || !height) return;
      camera.position.set(0, 5, Math.max(16, Math.max(7, 13 / (width / height)) / Math.tan(THREE.MathUtils.degToRad(24))));
      renderer.setSize(width, height); camera.aspect = width / height; camera.updateProjectionMatrix();
    });
    resize.observe(element);
    let frame = 0, priorSelection: string | null = null;
    const draw = () => {
      frame = requestAnimationFrame(draw);
      meshes.forEach(mesh => mesh.scale.setScalar(mesh.userData.id === selection.current ? 1.65 : 1));
      if (selection.current && selection.current !== priorSelection) {
        const pos = positions.get(selection.current);
        if (pos) controls.target.copy(pos);
      }
      priorSelection = selection.current;
      controls.update(); renderer.render(scene, camera);
    };
    draw();
    return () => {
      cancelAnimationFrame(frame); resize.disconnect(); controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", start); renderer.domElement.removeEventListener("pointerup", click);
      geometry.dispose(); lineGeometry.dispose(); lineMaterial.dispose(); materials.forEach(m=>m.dispose()); textures.forEach(t=>t.dispose());
      renderer.dispose(); renderer.domElement.remove();
    };
  }, [nodes, edges]);

  return <div className="infrastructure-scene" ref={mount} aria-label="Infrastructure graph. Use the entity list below for keyboard navigation.">
    {unavailable && <p>3D rendering unavailable. All entities and details are accessible in the list below.</p>}
  </div>;
}
