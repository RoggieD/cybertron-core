import { FormEvent, useEffect, useRef, useState } from "react";

import { getHealth } from "../api/core";
import { getStatusOverview, type StatusOverview } from "../api/status";
import { streamChat, type StreamEvent } from "../api/chat";
import {
  getSttStatus,
  getVoiceStatus,
  synthesizeSpeech,
  transcribeAudio,
} from "../api/voice";
import {
  connectCoreWebSocket,
  type CoreEvent,
} from "../api/websocket";

import "../styles.css";
import "../voice.css";

type ReactorState =
  | "IDLE"
  | "ROUTING"
  | "AGENT_ACTIVE"
  | "TOOL_ACTIVE"
  | "THINKING"
  | "COMPLETE"
  | "ERROR";

type VoiceState =
  | "READY"
  | "LISTENING"
  | "TRANSCRIBING"
  | "SPEAKING"
  | "OFFLINE"
  | "ERROR";
type TelemetryState = "HEALTHY" | "ELEVATED" | "WARNING";

const VAD_SPEECH_THRESHOLD = 0.018;
const VAD_SILENCE_MS = 1100;
const VAD_NO_SPEECH_TIMEOUT_MS = 8000;
const VAD_MAX_RECORDING_MS = 30000;

function getTelemetryState(
  overview: StatusOverview | null,
  error: boolean,
): TelemetryState {
  if (error) return "WARNING";
  if (!overview) return "HEALTHY";

  if (
    overview.services.unreachable > 0 ||
    overview.system.disk.usage_percent >= 95
  ) {
    return "WARNING";
  }

  if (
    overview.system.cpu.usage_percent >= 75 ||
    overview.system.memory.usage_percent >= 80 ||
    overview.system.disk.usage_percent >= 85
  ) {
    return "ELEVATED";
  }

  return "HEALTHY";
}

function microphoneSupported(): boolean {
  return Boolean(
    navigator.mediaDevices &&
    typeof navigator.mediaDevices.getUserMedia === "function" &&
    typeof window.MediaRecorder !== "undefined",
  );
}

function preferredRecordingMimeType(): string {
  if (typeof window.MediaRecorder === "undefined") return "";

  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/ogg",
  ];

  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function cleanSpeechText(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, " Code block omitted. ")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/\[(.*?)\]\([^)]*\)/g, "$1")
    .replace(/[*#>_~-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function selectSpeechText(text: string): string {
  const normalized = text.replace(/\r\n/g, "\n").trim();
  const preferredSections = ["ANALYSIS", "SUMMARY", "ANSWER"];

  for (const section of preferredSections) {
    const heading = new RegExp(
      `(?:^|\\n)\\s*(?:#{1,6}\\s*)?${section}\\s*:?\\s*\\n`,
      "i",
    );
    const match = heading.exec(normalized);

    if (match) {
      const start = match.index + match[0].length;
      const remainder = normalized.slice(start);
      const nextHeading = remainder.search(
        /\n\s*(?:#{1,6}\s*)?[A-Z][A-Z0-9 _/&-]{2,}\s*:?\s*\n/,
      );
      const sectionText = (
        nextHeading >= 0 ? remainder.slice(0, nextHeading) : remainder
      ).trim();

      if (sectionText) return cleanSpeechText(sectionText);
    }
  }

  const cleaned = cleanSpeechText(normalized);
  if (cleaned.length <= 650) return cleaned;

  const sentences = cleaned.match(/[^.!?]+[.!?]+/g) ?? [];
  let summary = "";

  for (const sentence of sentences) {
    const candidate = `${summary} ${sentence.trim()}`.trim();
    if (candidate.length > 525 && summary) break;
    summary = candidate;
    if (summary.length >= 350) break;
  }

  if (summary) return summary;

  const clipped = cleaned.slice(0, 525).replace(/\s+\S*$/, "").trim();
  return clipped ? `${clipped}…` : cleaned;
}

export default function DashboardPage() {
  const [apiStatus, setApiStatus] = useState("CHECKING");
  const [socketConnected, setSocketConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<CoreEvent | null>(null);
  const [overview, setOverview] = useState<StatusOverview | null>(null);
  const [overviewError, setOverviewError] = useState(false);

  const [prompt, setPrompt] = useState("");
  const [responseText, setResponseText] = useState("");
  const [reactorState, setReactorState] = useState<ReactorState>("IDLE");

  const [activeModel, setActiveModel] = useState("UNKNOWN");
  const [activeAgent, setActiveAgent] = useState("NONE");
  const [activeTool, setActiveTool] = useState("NONE");
  const [evalCount, setEvalCount] = useState<number | null>(null);
  const [durationMs, setDurationMs] = useState<number | null>(null);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [traceEventCount, setTraceEventCount] = useState(0);

  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [voiceState, setVoiceState] = useState<VoiceState>("OFFLINE");
  const [voiceProvider, setVoiceProvider] = useState("KOKORO");
  const [sttProvider, setSttProvider] = useState("WHISPER");
  const [sttReady, setSttReady] = useState(false);
  const [micSupported, setMicSupported] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const vadFrameRef = useRef<number | null>(null);
  const speechDetectedRef = useRef(false);
  const silenceStartedRef = useRef<number | null>(null);
  const recordingStartedRef = useRef<number | null>(null);

  function stopVoiceActivityDetection() {
    if (vadFrameRef.current !== null) {
      window.cancelAnimationFrame(vadFrameRef.current);
      vadFrameRef.current = null;
    }

    analyserRef.current?.disconnect();
    analyserRef.current = null;

    const context = audioContextRef.current;
    audioContextRef.current = null;
    if (context && context.state !== "closed") {
      void context.close();
    }
  }

  useEffect(() => {
    setMicSupported(microphoneSupported());

    void Promise.all([getVoiceStatus(), getSttStatus()])
      .then(([ttsStatus, sttStatus]) => {
        setVoiceProvider(ttsStatus.provider.toUpperCase());
        setSttProvider(sttStatus.provider.toUpperCase());
        setSttReady(sttStatus.reachable && sttStatus.authenticated);
        setVoiceState(ttsStatus.reachable ? "READY" : "OFFLINE");
      })
      .catch(() => {
        setSttReady(false);
        setVoiceState("OFFLINE");
      });

    return () => {
      stopVoiceActivityDetection();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      recorderRef.current = null;
      audioChunksRef.current = [];

      if (audioRef.current) {
        audioRef.current.pause();
        URL.revokeObjectURL(audioRef.current.src);
      }
    };
  }, []);

  useEffect(() => {
    let active = true;

    const refresh = async () => {
      try {
        const data = await getStatusOverview();
        if (active) {
          setOverview(data);
          setOverviewError(false);
        }
      } catch {
        if (active) setOverviewError(true);
      }
    };

    void refresh();
    const timer = window.setInterval(() => void refresh(), 5000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    void getHealth()
      .then(() => setApiStatus("ONLINE"))
      .catch(() => setApiStatus("OFFLINE"));

    const socket = connectCoreWebSocket(
      (event) => {
        setLastEvent(event);

        if (event.trace_id) {
          setTraceId(event.trace_id);
          setTraceEventCount((count) => count + 1);
        }

        switch (event.event_type) {
          case "prompt.received":
          case "router.started":
            setReactorState("ROUTING");
            break;
          case "agent.selected": {
            const agentName = event.metadata?.agent_name;
            const agentId = event.target?.id;
            if (typeof agentName === "string") setActiveAgent(agentName);
            else if (typeof agentId === "string") setActiveAgent(agentId);
            setReactorState("AGENT_ACTIVE");
            break;
          }
          case "agent.started":
            setReactorState("AGENT_ACTIVE");
            break;
          case "tool.started": {
            const toolId = event.target?.id;
            if (typeof toolId === "string") setActiveTool(toolId);
            setReactorState("TOOL_ACTIVE");
            break;
          }
          case "tool.completed":
            setReactorState("AGENT_ACTIVE");
            break;
          case "model.request_started":
          case "model.token":
            setReactorState("THINKING");
            break;
          case "model.request_completed":
          case "agent.completed":
            setReactorState("COMPLETE");
            break;
          case "response.generated":
            window.setTimeout(() => setReactorState("IDLE"), 1200);
            break;
          case "model.error":
            setReactorState("ERROR");
            break;
        }
      },
      setSocketConnected,
    );

    return () => socket.close();
  }, []);

  function stopSpeaking() {
    const audio = audioRef.current;
    if (!audio) return;

    audio.pause();
    audio.currentTime = 0;
    URL.revokeObjectURL(audio.src);
    audioRef.current = null;
    setVoiceState("READY");
  }

  async function speak(text: string) {
    const speechText = selectSpeechText(text);
    if (!voiceEnabled || !speechText || voiceState === "OFFLINE") return;

    try {
      setVoiceState("SPEAKING");
      const blob = await synthesizeSpeech(speechText);
      const url = URL.createObjectURL(blob);

      if (audioRef.current) {
        stopSpeaking();
      }

      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setVoiceState("READY");
      };
      audio.onerror = () => {
        URL.revokeObjectURL(url);
        audioRef.current = null;
        setVoiceState("ERROR");
      };
      await audio.play();
    } catch {
      setVoiceState("ERROR");
    }
  }

  async function processMessage(message: string) {
    const trimmed = message.trim();
    if (!trimmed) return;

    setPrompt(trimmed);
    setResponseText("");
    setEvalCount(null);
    setDurationMs(null);
    setTraceId(null);
    setTraceEventCount(0);
    setActiveAgent("ROUTING...");
    setActiveTool("NONE");
    setReactorState("ROUTING");

    let finalResponse = "";

    try {
      await streamChat(trimmed, (streamEvent: StreamEvent) => {
        if (streamEvent.model) setActiveModel(streamEvent.model);

        const eventWithAgent = streamEvent as StreamEvent & {
          agent_name?: string;
          agent?: string;
        };

        if (eventWithAgent.agent_name) setActiveAgent(eventWithAgent.agent_name);
        else if (eventWithAgent.agent) setActiveAgent(eventWithAgent.agent);

        if (streamEvent.event === "tool.result" && streamEvent.content) {
          finalResponse = streamEvent.content;
          setResponseText(streamEvent.content);
          setActiveModel("NOT USED");
          setEvalCount(null);
          setDurationMs(null);
        }

        if (streamEvent.event === "model.token" && streamEvent.content) {
          finalResponse += streamEvent.content;
          setResponseText((current) => current + streamEvent.content);
        }

        if (streamEvent.event === "model.request_completed") {
          if (typeof streamEvent.eval_count === "number") {
            setEvalCount(streamEvent.eval_count);
          }
          if (typeof streamEvent.total_duration === "number") {
            setDurationMs(streamEvent.total_duration / 1_000_000);
          }
        }

        if (streamEvent.event === "model.error") {
          setReactorState("ERROR");
          finalResponse = streamEvent.error ?? "Unknown model streaming error.";
          setResponseText(finalResponse);
        }
      });

      if (finalResponse) await speak(finalResponse);
    } catch (error) {
      setReactorState("ERROR");
      setResponseText(
        error instanceof Error ? error.message : "Unknown request failure.",
      );
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await processMessage(prompt);
  }

  function toggleVoice() {
    if (voiceEnabled && audioRef.current) {
      stopSpeaking();
    }
    setVoiceEnabled((enabled) => !enabled);
  }

  function stopListening() {
    stopVoiceActivityDetection();
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
  }

  function startVoiceActivityDetection(stream: MediaStream) {
    stopVoiceActivityDetection();

    const context = new AudioContext();
    const source = context.createMediaStreamSource(stream);
    const analyser = context.createAnalyser();
    analyser.fftSize = 1024;
    analyser.smoothingTimeConstant = 0.35;
    source.connect(analyser);

    audioContextRef.current = context;
    analyserRef.current = analyser;
    speechDetectedRef.current = false;
    silenceStartedRef.current = null;
    recordingStartedRef.current = performance.now();

    const samples = new Float32Array(analyser.fftSize);

    const monitor = () => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") {
        stopVoiceActivityDetection();
        return;
      }

      analyser.getFloatTimeDomainData(samples);
      let sumSquares = 0;
      for (const sample of samples) {
        sumSquares += sample * sample;
      }
      const rms = Math.sqrt(sumSquares / samples.length);
      const now = performance.now();
      const startedAt = recordingStartedRef.current ?? now;

      if (rms >= VAD_SPEECH_THRESHOLD) {
        speechDetectedRef.current = true;
        silenceStartedRef.current = null;
      } else if (speechDetectedRef.current) {
        if (silenceStartedRef.current === null) {
          silenceStartedRef.current = now;
        } else if (now - silenceStartedRef.current >= VAD_SILENCE_MS) {
          stopListening();
          return;
        }
      } else if (now - startedAt >= VAD_NO_SPEECH_TIMEOUT_MS) {
        stopListening();
        return;
      }

      if (now - startedAt >= VAD_MAX_RECORDING_MS) {
        stopListening();
        return;
      }

      vadFrameRef.current = window.requestAnimationFrame(monitor);
    };

    vadFrameRef.current = window.requestAnimationFrame(monitor);
  }

  async function startListening() {
    if (!micSupported || !sttReady) {
      setVoiceState("ERROR");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      audioChunksRef.current = [];
      speechDetectedRef.current = false;

      const mimeType = preferredRecordingMimeType();
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);

      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      recorder.onerror = () => {
        stopVoiceActivityDetection();
        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        recorderRef.current = null;
        setVoiceState("ERROR");
      };

      recorder.onstop = () => {
        stopVoiceActivityDetection();
        const chunks = audioChunksRef.current;
        const recordedType = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type: recordedType });
        const heardSpeech = speechDetectedRef.current;

        stream.getTracks().forEach((track) => track.stop());
        mediaStreamRef.current = null;
        recorderRef.current = null;
        audioChunksRef.current = [];
        recordingStartedRef.current = null;
        silenceStartedRef.current = null;

        if (!heardSpeech) {
          setVoiceState("READY");
          return;
        }

        if (!blob.size) {
          setVoiceState("ERROR");
          return;
        }

        setVoiceState("TRANSCRIBING");
        const extension = recordedType.includes("ogg") ? "ogg" : "webm";

        void transcribeAudio(blob, `microphone.${extension}`)
          .then(async (result) => {
            const transcript = result.text.trim();
            if (!transcript) {
              setVoiceState("READY");
              return;
            }

            setPrompt(transcript);
            setVoiceState("READY");
            await processMessage(transcript);
          })
          .catch(() => setVoiceState("ERROR"));
      };

      recorder.start();
      startVoiceActivityDetection(stream);
      setVoiceState("LISTENING");
    } catch {
      stopVoiceActivityDetection();
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
      mediaStreamRef.current = null;
      recorderRef.current = null;
      setVoiceState("ERROR");
    }
  }

  const telemetryState = getTelemetryState(overview, overviewError);
  const busy =
    reactorState === "ROUTING" ||
    reactorState === "AGENT_ACTIVE" ||
    reactorState === "TOOL_ACTIVE" ||
    reactorState === "THINKING";
  const displayedReactorState = voiceState === "SPEAKING" ? "SPEAKING" : reactorState;
  const microphoneReady = micSupported && sttReady;
  const voiceEngineOnline = [
    "READY",
    "LISTENING",
    "TRANSCRIBING",
    "SPEAKING",
  ].includes(voiceState);

  return (
    <main className="core-shell">
      <section className="header">
        <p className="eyebrow">CYBERTRON SYSTEMS</p>
        <h1>
          CyberTron <span>C.O.R.E.</span>
        </h1>
        <p className="subtitle">CyberTron Orchestration &amp; Reasoning Engine</p>
      </section>

      <section
        className={`reactor-panel reactor-${displayedReactorState.toLowerCase()} telemetry-${telemetryState.toLowerCase()}`}
      >
        <div className="reactor">
          <div className="reactor-core" />
          <div className="reactor-ring ring-one" />
          <div className="reactor-ring ring-two" />
          <div className="reactor-ring ring-three" />
        </div>

        <div className="state-label">
          {displayedReactorState}
          {displayedReactorState === "IDLE" && (
            <span className={`reactor-health telemetry-${telemetryState.toLowerCase()}`}>
              {" "}• {telemetryState}
            </span>
          )}
        </div>
      </section>

      <section className="conversation-panel">
        <form className="prompt-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Ask CyberTron..."
            disabled={busy}
          />
          <button type="submit" disabled={busy}>
            {busy ? "PROCESSING" : "SEND"}
          </button>
        </form>

        <div className="voice-controls">
          <button
            type="button"
            className={`voice-button ${voiceState === "LISTENING" ? "listening" : ""}`}
            onClick={() => {
              if (voiceState === "LISTENING") stopListening();
              else void startListening();
            }}
            disabled={
              busy ||
              !microphoneReady ||
              voiceState === "TRANSCRIBING" ||
              voiceState === "SPEAKING"
            }
            title={
              !micSupported
                ? "Microphone recording is not supported by this browser"
                : !sttReady
                  ? "Local Whisper STT is not ready"
                  : voiceState === "LISTENING"
                    ? "Listening with automatic silence detection; click to stop manually"
                    : "Record a command with local Whisper and automatic silence detection"
            }
          >
            {voiceState === "LISTENING"
              ? "● LISTENING • AUTO-STOP"
              : voiceState === "TRANSCRIBING"
                ? "… TRANSCRIBING"
                : "🎙 LISTEN"}
          </button>
          <button
            type="button"
            className={`voice-button ${voiceEnabled ? "active" : ""}`}
            onClick={toggleVoice}
          >
            {voiceEnabled ? "🔊 VOICE ON" : "🔇 VOICE OFF"}
          </button>
          {voiceState === "SPEAKING" && (
            <button
              type="button"
              className="voice-button"
              onClick={stopSpeaking}
              title="Stop Kokoro speech playback"
            >
              ⏹ STOP SPEAKING
            </button>
          )}
          <div className={`voice-state ${voiceState.toLowerCase()}`}>
            {voiceProvider} + {sttProvider} • {voiceState}
            {!micSupported ? " • MIC UNSUPPORTED" : !sttReady ? " • STT OFFLINE" : ""}
          </div>
        </div>

        <div className="response-panel">
          {responseText ? (
            <p>{responseText}</p>
          ) : (
            <p className="response-placeholder">C.O.R.E. awaiting input.</p>
          )}
        </div>
      </section>

      <section className="status-grid">
        <article>
          <span>CONTROL PLANE</span>
          <strong className={apiStatus === "ONLINE" ? "online" : ""}>
            {apiStatus}
          </strong>
        </article>
        <article>
          <span>EVENT BUS</span>
          <strong className={socketConnected ? "online" : ""}>
            {socketConnected ? "CONNECTED" : "OFFLINE"}
          </strong>
        </article>
        <article>
          <span>VOICE ENGINE</span>
          <strong className={voiceEngineOnline ? "online" : ""}>
            {voiceState}
          </strong>
        </article>
        <article>
          <span>SYSTEM HEALTH</span>
          <strong>{telemetryState}</strong>
        </article>
        <article>
          <span>ACTIVE MODEL</span>
          <strong>{activeModel}</strong>
        </article>
        <article>
          <span>ACTIVE AGENT</span>
          <strong>{activeAgent}</strong>
        </article>
        <article>
          <span>ACTIVE TOOL</span>
          <strong>{activeTool}</strong>
        </article>
        <article>
          <span>ACTIVE EVENT</span>
          <strong>{lastEvent?.event_type ?? "WAITING"}</strong>
        </article>
        <article>
          <span>TRACE EVENTS</span>
          <strong>{traceEventCount}</strong>
        </article>
        <article>
          <span>TRACE ID</span>
          <strong className="trace-id">{traceId ? traceId.slice(0, 8) : "—"}</strong>
        </article>
        <article>
          <span>EVAL TOKENS</span>
          <strong>{evalCount ?? "—"}</strong>
        </article>
        <article>
          <span>MODEL DURATION</span>
          <strong>{durationMs !== null ? `${durationMs.toFixed(0)} ms` : "—"}</strong>
        </article>
      </section>

      <footer>Local-first AI orchestration control plane</footer>
    </main>
  );
}