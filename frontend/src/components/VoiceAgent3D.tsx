import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

type VoiceVisualState =
  | "READY"
  | "LISTENING"
  | "TRANSCRIBING"
  | "SPEAKING"
  | "OFFLINE"
  | "ERROR";

type VoiceAgent3DProps = {
  active?: boolean;
};

const VOICE_STATES: VoiceVisualState[] = [
  "READY",
  "LISTENING",
  "TRANSCRIBING",
  "SPEAKING",
  "OFFLINE",
  "ERROR",
];

function readVoiceState(): VoiceVisualState {
  const element = document.querySelector(".voice-state");
  if (!element) return "OFFLINE";

  const text = element.textContent?.toUpperCase() ?? "";
  return VOICE_STATES.find((state) => text.includes(state)) ?? "READY";
}

function paletteForState(state: VoiceVisualState) {
  const neonGreen = document.documentElement.dataset.coreTheme === "neon-green";
  const base = neonGreen ? 0x39ff14 : 0x53e6ff;

  switch (state) {
    case "LISTENING":
      return { primary: 0xffd166, secondary: 0xff9f1c, energy: 1.35 };
    case "TRANSCRIBING":
      return { primary: 0x8f7dff, secondary: 0x53e6ff, energy: 1.55 };
    case "SPEAKING":
      return { primary: 0x64ffd8, secondary: 0xffffff, energy: 1.9 };
    case "ERROR":
      return { primary: 0xff4d6d, secondary: 0xff1744, energy: 1.7 };
    case "OFFLINE":
      return { primary: 0x44505a, secondary: 0x202830, energy: 0.35 };
    default:
      return { primary: base, secondary: neonGreen ? 0xaaff98 : 0xa7f6ff, energy: 0.8 };
  }
}

export default function VoiceAgent3D({ active = true }: VoiceAgent3DProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const visualStateRef = useRef<VoiceVisualState>("OFFLINE");
  const [voiceState, setVoiceState] = useState<VoiceVisualState>("OFFLINE");

  useEffect(() => {
    if (!active) return;

    const update = () => {
      const next = readVoiceState();
      visualStateRef.current = next;
      setVoiceState(next);
    };

    update();
    const observer = new MutationObserver(update);
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => observer.disconnect();
  }, [active]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !active) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 100);
    camera.position.set(0, 0.15, 5.6);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    const group = new THREE.Group();
    scene.add(group);

    const coreGeometry = new THREE.IcosahedronGeometry(1.05, 3);
    const coreMaterial = new THREE.MeshPhongMaterial({
      color: 0x39ff14,
      emissive: 0x143d12,
      emissiveIntensity: 1.1,
      transparent: true,
      opacity: 0.78,
      wireframe: true,
      shininess: 100,
    });
    const core = new THREE.Mesh(coreGeometry, coreMaterial);
    group.add(core);

    const innerGeometry = new THREE.IcosahedronGeometry(0.72, 2);
    const innerMaterial = new THREE.MeshBasicMaterial({
      color: 0xaaff98,
      transparent: true,
      opacity: 0.24,
    });
    const inner = new THREE.Mesh(innerGeometry, innerMaterial);
    group.add(inner);

    const ringMaterial = new THREE.MeshBasicMaterial({
      color: 0x39ff14,
      transparent: true,
      opacity: 0.5,
      side: THREE.DoubleSide,
    });

    const ringOne = new THREE.Mesh(
      new THREE.TorusGeometry(1.4, 0.018, 8, 96),
      ringMaterial.clone(),
    );
    ringOne.rotation.x = Math.PI / 2.6;
    group.add(ringOne);

    const ringTwo = new THREE.Mesh(
      new THREE.TorusGeometry(1.65, 0.012, 8, 96),
      ringMaterial.clone(),
    );
    ringTwo.rotation.y = Math.PI / 2.25;
    group.add(ringTwo);

    const particlesGeometry = new THREE.BufferGeometry();
    const particleCount = 150;
    const positions = new Float32Array(particleCount * 3);
    for (let i = 0; i < particleCount; i += 1) {
      const radius = 1.9 + Math.random() * 0.75;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = radius * Math.cos(phi);
    }
    particlesGeometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    const particlesMaterial = new THREE.PointsMaterial({
      color: 0x39ff14,
      size: 0.025,
      transparent: true,
      opacity: 0.55,
    });
    const particles = new THREE.Points(particlesGeometry, particlesMaterial);
    group.add(particles);

    const ambient = new THREE.AmbientLight(0xffffff, 0.55);
    scene.add(ambient);
    const key = new THREE.PointLight(0x53e6ff, 3.2, 12);
    key.position.set(2.5, 2.5, 3.5);
    scene.add(key);

    const resize = () => {
      const width = Math.max(mount.clientWidth, 1);
      const height = Math.max(mount.clientHeight, 1);
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    };
    resize();
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(mount);

    const clock = new THREE.Clock();
    let frame = 0;

    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const state = visualStateRef.current;
      const palette = paletteForState(state);

      const primary = new THREE.Color(palette.primary);
      const secondary = new THREE.Color(palette.secondary);
      coreMaterial.color.lerp(primary, 0.09);
      coreMaterial.emissive.lerp(primary.clone().multiplyScalar(0.22), 0.08);
      innerMaterial.color.lerp(secondary, 0.08);
      (ringOne.material as THREE.MeshBasicMaterial).color.lerp(primary, 0.08);
      (ringTwo.material as THREE.MeshBasicMaterial).color.lerp(secondary, 0.08);
      particlesMaterial.color.lerp(primary, 0.08);
      key.color.lerp(secondary, 0.08);

      const pulseRate = state === "SPEAKING" ? 7.5 : state === "LISTENING" ? 4.2 : 2.1;
      const pulse = 1 + Math.sin(elapsed * pulseRate) * 0.055 * palette.energy;
      core.scale.setScalar(pulse);
      inner.scale.setScalar(0.96 + Math.sin(elapsed * pulseRate + 1.2) * 0.07 * palette.energy);

      core.rotation.x += 0.0028 * palette.energy;
      core.rotation.y += 0.0045 * palette.energy;
      inner.rotation.x -= 0.0032 * palette.energy;
      inner.rotation.z += 0.0025 * palette.energy;
      ringOne.rotation.z += 0.006 * palette.energy;
      ringTwo.rotation.x -= 0.004 * palette.energy;
      particles.rotation.y -= 0.0018 * palette.energy;
      particles.rotation.x = Math.sin(elapsed * 0.22) * 0.12;

      if (state === "SPEAKING") {
        group.position.y = Math.sin(elapsed * 5.5) * 0.035;
        ringOne.scale.setScalar(1 + Math.sin(elapsed * 8.5) * 0.045);
      } else if (state === "LISTENING") {
        group.position.y = Math.sin(elapsed * 1.8) * 0.025;
        ringOne.scale.setScalar(1 + Math.sin(elapsed * 3.5) * 0.025);
      } else {
        group.position.y = Math.sin(elapsed * 1.2) * 0.018;
        ringOne.scale.setScalar(1);
      }

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      window.cancelAnimationFrame(frame);
      resizeObserver.disconnect();
      renderer.dispose();
      coreGeometry.dispose();
      innerGeometry.dispose();
      particlesGeometry.dispose();
      coreMaterial.dispose();
      innerMaterial.dispose();
      ringOne.geometry.dispose();
      ringTwo.geometry.dispose();
      (ringOne.material as THREE.Material).dispose();
      (ringTwo.material as THREE.Material).dispose();
      particlesMaterial.dispose();
      if (renderer.domElement.parentElement === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [active]);

  if (!active) return null;

  return (
    <aside className={`voice-agent-3d voice-agent-${voiceState.toLowerCase()}`}>
      <div className="voice-agent-heading">
        <span>VOICE AGENT</span>
        <strong>{voiceState}</strong>
      </div>
      <div ref={mountRef} className="voice-agent-canvas" aria-hidden="true" />
      <div className="voice-agent-caption">
        <span>WHISPER</span>
        <i>→</i>
        <span>C.O.R.E.</span>
        <i>→</i>
        <span>KOKORO</span>
      </div>
    </aside>
  );
}
