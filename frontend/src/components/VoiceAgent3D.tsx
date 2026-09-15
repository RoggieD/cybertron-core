import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import * as THREE from "three";

import { getModelState, setActiveModel } from "../api/models";
import { getAgents, type AgentSummary } from "../api/agents";

export type VoiceVisualState =
  | "READY"
  | "LISTENING"
  | "TRANSCRIBING"
  | "SPEAKING"
  | "OFFLINE"
  | "ERROR";

export type ConversationExchange = { prompt: string; response: string };

type VoiceAgent3DProps = {
  conversationHistory?: ConversationExchange[];
  active?: boolean;
  activeAgent?: string;
  activeTool?: string;
  activeModel?: string;
  orchestrationState?: string;
  speechAnalyser?: AnalyserNode | null;
  voiceState?: VoiceVisualState;
  lastTranscript?: string;
  lastResponse?: string;
  agentMode?: string;
  requestPending?: boolean;
};

export type VoiceAgentRuntimeState = {
  conversationHistory?: ConversationExchange[];
  activeAgent: string;
  activeTool: string;
  activeModel: string;
  orchestrationState: string;
  speechAnalyser: AnalyserNode | null;
  voiceState: VoiceVisualState;
  lastTranscript: string;
  lastResponse: string;
  agentMode: string;
  requestPending: boolean;
};

type WidgetPosition = {
  x: number;
  y: number;
};

type WidgetSize = {
  width: number;
  height: number;
};

const DEFAULT_WIDGET_SIZE: WidgetSize = { width: 270, height: 330 };
const MIN_WIDGET_SIZE: WidgetSize = { width: 240, height: 260 };
const MAX_WIDGET_SIZE: WidgetSize = { width: 520, height: 620 };
const WIDGET_MARGIN = 12;
const WIDGET_SNAP_DISTANCE = 28;
const WIDGET_STORAGE_KEY = "cybertron.voice-agent.position";
const WIDGET_MINIMIZED_STORAGE_KEY = "cybertron.voice-agent.minimized";
const WIDGET_SIZE_STORAGE_KEY = "cybertron.voice-agent.size";
const WIDGET_CONVERSATION_STORAGE_KEY = "cybertron.voice-agent.conversation-open";

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

function clampSize(size: WidgetSize): WidgetSize {
  return {
    width: Math.min(
      Math.max(size.width, MIN_WIDGET_SIZE.width),
      Math.min(MAX_WIDGET_SIZE.width, window.innerWidth - WIDGET_MARGIN * 2),
    ),
    height: Math.min(
      Math.max(size.height, MIN_WIDGET_SIZE.height),
      Math.min(MAX_WIDGET_SIZE.height, window.innerHeight - WIDGET_MARGIN * 2),
    ),
  };
}

function clampPosition(position: WidgetPosition, size: WidgetSize): WidgetPosition {
  const maxX = Math.max(WIDGET_MARGIN, window.innerWidth - size.width - WIDGET_MARGIN);
  const maxY = Math.max(WIDGET_MARGIN, window.innerHeight - size.height - WIDGET_MARGIN);

  return {
    x: Math.min(Math.max(position.x, WIDGET_MARGIN), maxX),
    y: Math.min(Math.max(position.y, WIDGET_MARGIN), maxY),
  };
}

function defaultPosition(size: WidgetSize): WidgetPosition {
  return clampPosition({
    x: window.innerWidth - size.width - 22,
    y: window.innerHeight - size.height - 22,
  }, size);
}

function storedSize(): WidgetSize {
  try {
    const raw = window.localStorage.getItem(WIDGET_SIZE_STORAGE_KEY);
    if (!raw) return DEFAULT_WIDGET_SIZE;

    const parsed = JSON.parse(raw) as Partial<WidgetSize>;
    if (typeof parsed.width !== "number" || typeof parsed.height !== "number") {
      return DEFAULT_WIDGET_SIZE;
    }
    return clampSize({ width: parsed.width, height: parsed.height });
  } catch {
    return DEFAULT_WIDGET_SIZE;
  }
}

function storedPosition(size: WidgetSize): WidgetPosition {
  try {
    const raw = window.localStorage.getItem(WIDGET_STORAGE_KEY);
    if (!raw) return defaultPosition(size);

    const parsed = JSON.parse(raw) as Partial<WidgetPosition>;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") {
      return defaultPosition(size);
    }

    return clampPosition({ x: parsed.x, y: parsed.y }, size);
  } catch {
    return defaultPosition(size);
  }
}

function snapPosition(position: WidgetPosition, size: WidgetSize): WidgetPosition {
  const clamped = clampPosition(position, size);
  const right = window.innerWidth - size.width - WIDGET_MARGIN;
  const bottom = window.innerHeight - size.height - WIDGET_MARGIN;

  return {
    x: clamped.x <= WIDGET_MARGIN + WIDGET_SNAP_DISTANCE
      ? WIDGET_MARGIN
      : clamped.x >= right - WIDGET_SNAP_DISTANCE
        ? right
        : clamped.x,
    y: clamped.y <= WIDGET_MARGIN + WIDGET_SNAP_DISTANCE
      ? WIDGET_MARGIN
      : clamped.y >= bottom - WIDGET_SNAP_DISTANCE
        ? bottom
        : clamped.y,
  };
}

function storedMinimized(): boolean {
  try {
    return window.localStorage.getItem(WIDGET_MINIMIZED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function storedConversationOpen(): boolean {
  try {
    return window.localStorage.getItem(WIDGET_CONVERSATION_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function displayValue(value: string | undefined, fallback: string) {
  const normalized = value?.trim();
  return normalized && normalized !== "NONE" ? normalized : fallback;
}

function sendVoiceAction(
  action: "listen" | "stop-speaking" | "submit" | "cancel",
  message?: string,
) {
  window.dispatchEvent(
    new CustomEvent("cybertron:voice-action", { detail: { action, message } }),
  );
}

export default function VoiceAgent3D({
  active = true,
  activeAgent,
  activeTool,
  activeModel,
  orchestrationState = "IDLE",
  speechAnalyser = null,
  voiceState: controlledVoiceState,
  lastTranscript = "",
  lastResponse = "",
  conversationHistory = [],
  agentMode = "auto",
  requestPending = false,
}: VoiceAgent3DProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const visualStateRef = useRef<VoiceVisualState>("OFFLINE");
  const dragRef = useRef<{
    pointerId: number;
    offsetX: number;
    offsetY: number;
  } | null>(null);
  const resizeRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    startWidth: number;
    startHeight: number;
  } | null>(null);
  const [voiceState, setVoiceState] = useState<VoiceVisualState>("OFFLINE");
  const [size, setSize] = useState<WidgetSize>(() => storedSize());
  const [position, setPosition] = useState<WidgetPosition>(() => storedPosition(size));
  const [minimized, setMinimized] = useState(() => storedMinimized());
  const [conversationOpen, setConversationOpen] = useState(() => storedConversationOpen());
  const [chatInput, setChatInput] = useState("");
  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState(activeModel ?? "");
  const [modelControlState, setModelControlState] = useState<
    "LOADING" | "READY" | "SWITCHING" | "ERROR"
  >("LOADING");
  const [modelControlError, setModelControlError] = useState("");
  const [agentOptions, setAgentOptions] = useState<AgentSummary[]>([]);
  const [agentControlState, setAgentControlState] = useState<"LOADING" | "READY" | "ERROR">(
    "LOADING",
  );
  const operationActive = requestPending;
  const operationActiveRef = useRef(operationActive);
  const orchestrationStateRef = useRef(orchestrationState);
  const speechAnalyserRef = useRef<AnalyserNode | null>(speechAnalyser);
  operationActiveRef.current = operationActive;
  orchestrationStateRef.current = orchestrationState;
  speechAnalyserRef.current = speechAnalyser;

  useEffect(() => {
    if (!active) return;

    if (controlledVoiceState) {
      visualStateRef.current = controlledVoiceState;
      setVoiceState(controlledVoiceState);
      return;
    }

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
  }, [active, controlledVoiceState]);

  useEffect(() => {
    const onResize = () => {
      setSize((current) => {
        const next = clampSize(current);
        setPosition((currentPosition) => clampPosition(currentPosition, next));
        return next;
      });
    };
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    let mounted = true;
    void getAgents()
      .then((result) => {
        if (!mounted) return;
        setAgentOptions(result.agents);
        setAgentControlState("READY");
      })
      .catch(() => {
        if (mounted) setAgentControlState("ERROR");
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    window.localStorage.setItem(WIDGET_STORAGE_KEY, JSON.stringify(position));
  }, [position]);

  useEffect(() => {
    window.localStorage.setItem(WIDGET_SIZE_STORAGE_KEY, JSON.stringify(size));
  }, [size]);

  useEffect(() => {
    window.localStorage.setItem(WIDGET_MINIMIZED_STORAGE_KEY, String(minimized));
  }, [minimized]);

  useEffect(() => {
    window.localStorage.setItem(
      WIDGET_CONVERSATION_STORAGE_KEY,
      String(conversationOpen),
    );
  }, [conversationOpen]);

  useEffect(() => {
    let mounted = true;
    void getModelState()
      .then((state) => {
        if (!mounted) return;
        setModelOptions(state.available_models);
        setSelectedModel(state.active_model);
        setModelControlState("READY");
        setModelControlError("");
      })
      .catch((error) => {
        if (!mounted) return;
        setModelControlState("ERROR");
        setModelControlError(error instanceof Error ? error.message : "Model control unavailable.");
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount || !active || minimized) return;

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

    const scanMaterial = new THREE.MeshBasicMaterial({
      color: 0x53e6ff,
      transparent: true,
      opacity: 0.12,
    });
    const scanRing = new THREE.Mesh(
      new THREE.TorusGeometry(1.18, 0.012, 8, 72),
      scanMaterial,
    );
    scanRing.rotation.x = Math.PI / 2;
    group.add(scanRing);

    const satelliteGeometry = new THREE.SphereGeometry(0.09, 16, 16);
    const agentMaterial = new THREE.MeshBasicMaterial({
      color: 0x53e6ff,
      transparent: true,
      opacity: 0.18,
    });
    const toolMaterial = new THREE.MeshBasicMaterial({
      color: 0xffd166,
      transparent: true,
      opacity: 0.18,
    });
    const modelMaterial = new THREE.MeshBasicMaterial({
      color: 0x8f7dff,
      transparent: true,
      opacity: 0.18,
    });
    const agentNode = new THREE.Mesh(satelliteGeometry, agentMaterial);
    const toolNode = new THREE.Mesh(satelliteGeometry, toolMaterial);
    const modelNode = new THREE.Mesh(satelliteGeometry, modelMaterial);
    group.add(agentNode, toolNode, modelNode);

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
    const audioSamples = new Uint8Array(128);
    let smoothedAudioEnergy = 0;
    let frame = 0;

    const animate = () => {
      frame = window.requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();
      const state = visualStateRef.current;
      const palette = paletteForState(state);
      const analyser = speechAnalyserRef.current;
      let audioEnergy = 0;

      if (analyser && state === "SPEAKING") {
        analyser.getByteFrequencyData(audioSamples);
        let total = 0;
        for (const sample of audioSamples) total += sample;
        audioEnergy = Math.min(1, (total / audioSamples.length / 255) * 4.2);
      }
      smoothedAudioEnergy += (audioEnergy - smoothedAudioEnergy) * 0.24;

      const primary = new THREE.Color(palette.primary);
      const secondary = new THREE.Color(palette.secondary);
      coreMaterial.color.lerp(primary, 0.09);
      coreMaterial.emissive.lerp(primary.clone().multiplyScalar(0.22), 0.08);
      innerMaterial.color.lerp(secondary, 0.08);
      (ringOne.material as THREE.MeshBasicMaterial).color.lerp(primary, 0.08);
      (ringTwo.material as THREE.MeshBasicMaterial).color.lerp(secondary, 0.08);
      particlesMaterial.color.lerp(primary, 0.08);
      key.color.lerp(secondary, 0.08);

      const isOperating = operationActiveRef.current;
      const operationStage = orchestrationStateRef.current;
      const operationEnergy = isOperating ? 1.28 : 1;
      const pulseRate = state === "SPEAKING" ? 7.5 : state === "LISTENING" ? 4.2 : isOperating ? 3.2 : 2.1;
      const pulse = 1 + Math.sin(elapsed * pulseRate) * 0.055 * palette.energy * operationEnergy + smoothedAudioEnergy * 0.2;
      core.scale.setScalar(pulse);
      inner.scale.setScalar(0.96 + Math.sin(elapsed * pulseRate + 1.2) * 0.07 * palette.energy + smoothedAudioEnergy * 0.26);

      core.rotation.x += 0.0028 * palette.energy;
      core.rotation.y += 0.0045 * palette.energy * operationEnergy;
      inner.rotation.x -= 0.0032 * palette.energy;
      inner.rotation.z += 0.0025 * palette.energy;
      ringOne.rotation.z += 0.006 * palette.energy * operationEnergy;
      ringTwo.rotation.x -= 0.004 * palette.energy * operationEnergy;
      particles.rotation.y -= 0.0018 * palette.energy;
      particles.rotation.x = Math.sin(elapsed * 0.22) * 0.12;
      particlesMaterial.size = 0.025 + smoothedAudioEnergy * 0.055;
      particlesMaterial.opacity = 0.55 + smoothedAudioEnergy * 0.35;

      const agentActive = ["AGENT_ACTIVE", "TOOL_ACTIVE", "THINKING"].includes(operationStage);
      const toolActive = operationStage === "TOOL_ACTIVE";
      const modelActive = operationStage === "THINKING";
      const satelliteStates = [
        { node: agentNode, material: agentMaterial, active: agentActive, radius: 1.72, speed: 0.72, phase: 0 },
        { node: toolNode, material: toolMaterial, active: toolActive, radius: 1.96, speed: -0.58, phase: 2.1 },
        { node: modelNode, material: modelMaterial, active: modelActive, radius: 2.2, speed: 0.46, phase: 4.2 },
      ];

      satelliteStates.forEach(({ node, material, active: nodeActive, radius, speed, phase }) => {
        const angle = elapsed * speed + phase;
        node.position.set(
          Math.cos(angle) * radius,
          Math.sin(angle * 1.45) * 0.72,
          Math.sin(angle) * radius * 0.46,
        );
        material.opacity = THREE.MathUtils.lerp(material.opacity, nodeActive ? 0.96 : 0.16, 0.12);
        const nodeScale = nodeActive
          ? 1.15 + Math.sin(elapsed * 6 + phase) * 0.22
          : 0.72;
        node.scale.setScalar(nodeScale);
      });

      scanRing.position.y = ((elapsed * (isOperating ? 0.85 : 0.3)) % 2.5) - 1.25;
      scanMaterial.opacity = THREE.MathUtils.lerp(
        scanMaterial.opacity,
        isOperating ? 0.48 : 0.1,
        0.08,
      );
      scanRing.scale.setScalar(0.72 + (1 - Math.abs(scanRing.position.y) / 1.4) * 0.42);

      if (state === "SPEAKING") {
        group.position.y = Math.sin(elapsed * 5.5) * 0.035 + smoothedAudioEnergy * 0.025;
        ringOne.scale.setScalar(1 + Math.sin(elapsed * 8.5) * 0.045 + smoothedAudioEnergy * 0.2);
        ringTwo.scale.setScalar(1 + smoothedAudioEnergy * 0.12);
      } else if (state === "LISTENING") {
        group.position.y = Math.sin(elapsed * 1.8) * 0.025;
        ringOne.scale.setScalar(1 + Math.sin(elapsed * 3.5) * 0.025);
        ringTwo.scale.setScalar(1);
      } else {
        group.position.y = Math.sin(elapsed * 1.2) * 0.018;
        ringOne.scale.setScalar(1);
        ringTwo.scale.setScalar(1);
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
      scanRing.geometry.dispose();
      satelliteGeometry.dispose();
      (ringOne.material as THREE.Material).dispose();
      (ringTwo.material as THREE.Material).dispose();
      scanMaterial.dispose();
      agentMaterial.dispose();
      toolMaterial.dispose();
      modelMaterial.dispose();
      particlesMaterial.dispose();
      if (renderer.domElement.parentElement === mount) {
        mount.removeChild(renderer.domElement);
      }
    };
  }, [active, minimized]);

  function beginDrag(event: ReactPointerEvent<HTMLDivElement>) {
    if (event.button !== 0 || window.innerWidth <= 900) return;

    const widget = event.currentTarget.closest<HTMLElement>(".voice-agent-3d");
    if (!widget) return;

    const bounds = widget.getBoundingClientRect();
    dragRef.current = {
      pointerId: event.pointerId,
      offsetX: event.clientX - bounds.left,
      offsetY: event.clientY - bounds.top,
    };

    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.classList.add("voice-agent-dragging");
  }

  function continueDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    setPosition(
      clampPosition({
        x: event.clientX - drag.offsetX,
        y: event.clientY - drag.offsetY,
      }, minimized ? { width: size.width, height: 42 } : size),
    );
  }

  function endDrag(event: ReactPointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;

    dragRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    document.body.classList.remove("voice-agent-dragging");
    setPosition((current) => snapPosition(
      current,
      minimized ? { width: size.width, height: 42 } : size,
    ));
  }

  function resetPosition() {
    setPosition(defaultPosition(size));
  }

  function beginResize(event: ReactPointerEvent<HTMLButtonElement>) {
    if (event.button !== 0 || minimized) return;
    resizeRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startWidth: size.width,
      startHeight: size.height,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
    document.body.classList.add("voice-agent-resizing");
  }

  function continueResize(event: ReactPointerEvent<HTMLButtonElement>) {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;

    const next = clampSize({
      width: resize.startWidth + event.clientX - resize.startX,
      height: resize.startHeight + event.clientY - resize.startY,
    });
    const available = {
      width: Math.min(next.width, window.innerWidth - position.x - WIDGET_MARGIN),
      height: Math.min(next.height, window.innerHeight - position.y - WIDGET_MARGIN),
    };
    setSize(clampSize(available));
  }

  function endResize(event: ReactPointerEvent<HTMLButtonElement>) {
    const resize = resizeRef.current;
    if (!resize || resize.pointerId !== event.pointerId) return;
    resizeRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    document.body.classList.remove("voice-agent-resizing");
  }

  function submitChat(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = chatInput.trim();
    if (!message || operationActive) return;
    sendVoiceAction("submit", message);
    setChatInput("");
  }

  async function changeModel(model: string) {
    if (!model || operationActive || model === selectedModel) return;
    const previous = selectedModel;
    setSelectedModel(model);
    setModelControlState("SWITCHING");
    setModelControlError("");

    try {
      const state = await setActiveModel(model);
      setSelectedModel(state.active_model);
      setModelOptions(state.available_models);
      setModelControlState("READY");
      window.dispatchEvent(
        new CustomEvent("cybertron:model-changed", {
          detail: { model: state.active_model },
        }),
      );
    } catch (error) {
      setSelectedModel(previous);
      setModelControlState("ERROR");
      setModelControlError(error instanceof Error ? error.message : "Model switch failed.");
    }
  }

  if (!active) return null;

  return (
    <aside
      className={`voice-agent-3d voice-agent-${voiceState.toLowerCase()} ${operationActive ? "voice-agent-operating" : ""} ${minimized ? "voice-agent-minimized" : ""} ${conversationOpen ? "voice-agent-conversation-open" : ""}`}
      style={{
        left: position.x,
        top: position.y,
        width: size.width,
        height: minimized ? 42 : size.height,
      }}
    >
      <div
        className="voice-agent-heading voice-agent-drag-handle"
        onPointerDown={beginDrag}
        onPointerMove={continueDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onDoubleClick={resetPosition}
        title="Drag to move • double-click to reset position"
      >
        <span>VOICE AGENT</span>
        <div className="voice-agent-heading-actions">
          <strong>{voiceState}</strong>
          <button
            type="button"
            onPointerDown={(event) => event.stopPropagation()}
            onDoubleClick={(event) => event.stopPropagation()}
            onClick={() => setConversationOpen((current) => !current)}
            aria-label={conversationOpen ? "Hide conversation" : "Show conversation"}
            aria-pressed={conversationOpen}
            title={conversationOpen ? "Hide conversation" : "Show conversation"}
          >
            {conversationOpen ? "CORE" : "CHAT"}
          </button>
          <button
            type="button"
            onPointerDown={(event) => event.stopPropagation()}
            onDoubleClick={(event) => event.stopPropagation()}
            onClick={() => setMinimized((current) => !current)}
            aria-label={minimized ? "Restore Voice Agent" : "Minimize Voice Agent"}
            title={minimized ? "Restore Voice Agent" : "Minimize Voice Agent"}
          >
            {minimized ? "OPEN" : "MIN"}
          </button>
        </div>
      </div>
      <div className="voice-agent-operation" aria-live="polite">
        <div>
          <span>AGENT</span>
          <strong>{displayValue(activeAgent, "STANDBY")}</strong>
        </div>
        <div>
          <span>TOOL</span>
          <strong>{displayValue(activeTool, "—")}</strong>
        </div>
        <div>
          <span>MODEL</span>
          <strong>{displayValue(activeModel, "—")}</strong>
        </div>
        <div>
          <span>STATE</span>
          <strong>{orchestrationState.replaceAll("_", " ")}</strong>
        </div>
      </div>
      <div ref={mountRef} className="voice-agent-canvas" aria-hidden="true" />
      {conversationOpen && (
        <div className="voice-agent-conversation" aria-live="polite">
          <div className="voice-agent-model-control">
            <label htmlFor="voice-agent-model">ACTIVE MODEL</label>
            <select
              id="voice-agent-model"
              value={selectedModel}
              onChange={(event) => void changeModel(event.target.value)}
              disabled={
                operationActive ||
                modelControlState === "LOADING" ||
                modelControlState === "SWITCHING" ||
                modelOptions.length === 0
              }
            >
              {modelOptions.length === 0 && (
                <option value={selectedModel}>{selectedModel || "UNAVAILABLE"}</option>
              )}
              {modelOptions.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
            </select>
            <strong>{modelControlState}</strong>
          </div>
          {modelControlError && (
            <div className="voice-agent-model-error" title={modelControlError}>
              MODEL CONTROL ERROR
            </div>
          )}
          <div className="voice-agent-model-control voice-agent-agent-control">
            <label htmlFor="voice-agent-mode">AGENT MODE</label>
            <select
              id="voice-agent-mode"
              value={agentMode}
              onChange={(event) => {
                window.dispatchEvent(
                  new CustomEvent("cybertron:agent-mode-changed", {
                    detail: { agentId: event.target.value },
                  }),
                );
              }}
              disabled={operationActive || agentControlState !== "READY"}
            >
              <option value="auto">AUTO ROUTER</option>
              {agentOptions.map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
            <strong>{agentControlState}</strong>
          </div>
          <div className="voice-agent-conversation-log">
            <section>
              <span>YOU / WHISPER</span>
              <p>{lastTranscript || "Awaiting command."}</p>
            </section>
            <section>
              <span>C.O.R.E.</span>
              <p>{lastResponse || "Awaiting response."}</p>
            </section>
            {conversationHistory.slice().reverse().map((exchange, index) => (
              <div key={conversationHistory.length - 1 - index}>
                <section><span>YOU</span><p>{exchange.prompt}</p></section>
                <section><span>C.O.R.E.</span><p>{exchange.response || "[No response]"}</p></section>
              </div>
            ))}
          </div>
          <form className="voice-agent-chat-form" onSubmit={submitChat}>
            <input
              type="text"
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              placeholder="Command C.O.R.E.…"
              disabled={operationActive}
              aria-label="Command C.O.R.E."
            />
            <button type="submit" disabled={operationActive || !chatInput.trim()}>
              SEND
            </button>
          </form>
        </div>
      )}
      <div className="voice-agent-controls">
        {requestPending && (
          <button type="button" onClick={() => sendVoiceAction("cancel")}>
            CANCEL REQUEST
          </button>
        )}
        {voiceState === "SPEAKING" ? (
          <button type="button" onClick={() => sendVoiceAction("stop-speaking")}>
            ■ STOP SPEAKING
          </button>
        ) : (
          <button
            type="button"
            className={voiceState === "LISTENING" ? "active" : ""}
            onClick={() => sendVoiceAction("listen")}
            disabled={!["READY", "LISTENING"].includes(voiceState)}
          >
            {voiceState === "LISTENING" ? "■ STOP LISTENING" : "● LISTEN"}
          </button>
        )}
      </div>
      <div className="voice-agent-caption">
        <span>WHISPER</span>
        <i>→</i>
        <span>C.O.R.E.</span>
        <i>→</i>
        <span>KOKORO</span>
      </div>
      {!minimized && (
        <button
          type="button"
          className="voice-agent-resize-handle"
          onPointerDown={beginResize}
          onPointerMove={continueResize}
          onPointerUp={endResize}
          onPointerCancel={endResize}
          aria-label="Resize Voice Agent"
          title="Drag to resize"
        />
      )}
    </aside>
  );
}
