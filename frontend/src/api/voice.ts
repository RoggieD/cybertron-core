export type VoiceStatus = {
  provider: string;
  base_url: string;
  default_voice: string;
  reachable: boolean;
};

export type SttStatus = {
  provider: string;
  base_url: string;
  model: string;
  authenticated: boolean;
  reachable: boolean;
};

export type TranscriptionResult = {
  text: string;
  provider: string;
  model: string;
};

function valueFor(text: string, label: string): string | null {
  const escaped = label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = text.match(new RegExp(`${escaped}:\\s*([^|]+?)(?=\\s+[A-Z][A-Za-z ]{1,24}:|$)`, "i"));
  return match?.[1]?.trim() ?? null;
}

function firstMatch(text: string, pattern: RegExp): string | null {
  return text.match(pattern)?.[1]?.trim() ?? null;
}

function toolAwareSpeechText(text: string): string {
  const normalized = text.replace(/\s+/g, " ").trim();
  const upper = normalized.toUpperCase();

  if (upper.includes("SYSTEM OVERVIEW") || upper.includes("SYSTEM STATUS")) {
    const host = valueFor(normalized, "Host") ?? valueFor(normalized, "Hostname");
    const cpu = firstMatch(normalized, /CPU usage:\s*([0-9.]+%)/i);
    const memory = firstMatch(normalized, /Memory usage:\s*([0-9.]+%)/i);
    const disk = firstMatch(normalized, /Disk usage:\s*([0-9.]+%)/i);
    const running = firstMatch(normalized, /Running:\s*(\d+)/i);
    const containers = firstMatch(normalized, /Containers:\s*(\d+)/i);
    const healthy = firstMatch(normalized, /Healthy:\s*(\d+\/\d+)/i);
    const unreachable = firstMatch(normalized, /Unreachable:\s*(\d+)/i);

    const parts: string[] = [];
    parts.push(`${host ?? "The system"} status is verified.`);

    const utilization: string[] = [];
    if (cpu) utilization.push(`CPU is ${cpu}`);
    if (memory) utilization.push(`memory is ${memory}`);
    if (disk) utilization.push(`disk usage is ${disk}`);
    if (utilization.length) parts.push(`${utilization.join(", ")}.`);

    if (running && containers) {
      parts.push(`${running} of ${containers} containers are running.`);
    }

    if (healthy) {
      parts.push(`${healthy} monitored services are healthy.`);
    }

    if (unreachable && Number(unreachable) > 0) {
      parts.push(`${unreachable} monitored service${unreachable === "1" ? " is" : "s are"} currently unreachable.`);
    } else if (unreachable === "0") {
      parts.push("All monitored services are reachable.");
    }

    return parts.join(" ");
  }

  if (upper.includes("SECURITY") && upper.includes("VERIFIED")) {
    const approved = firstMatch(normalized, /Approved:\s*(\d+)/i);
    const drift = firstMatch(normalized, /(?:Policy drift|Drift):\s*(\d+)/i);
    const learned = firstMatch(normalized, /Learned(?: only)?:\s*(\d+)/i);
    const parts = ["Security status is verified."];
    if (approved) parts.push(`${approved} endpoints are approved.`);
    if (drift) parts.push(`${drift} policy drift item${drift === "1" ? " is" : "s are"} present.`);
    if (learned) parts.push(`${learned} learned-only endpoint${learned === "1" ? " remains" : "s remain"} for review.`);
    return parts.join(" ");
  }

  if (upper.includes("INCIDENT") && upper.includes("VERIFIED")) {
    const active = firstMatch(normalized, /Active:\s*(\d+)/i);
    const acknowledged = firstMatch(normalized, /Acknowledged:\s*(\d+)/i);
    const critical = firstMatch(normalized, /Critical:\s*(\d+)/i);
    const parts = ["Incident status is verified."];
    if (active) parts.push(`${active} incident${active === "1" ? " is" : "s are"} active.`);
    if (critical && Number(critical) > 0) parts.push(`${critical} ${critical === "1" ? "is" : "are"} critical.`);
    if (acknowledged) parts.push(`${acknowledged} incident${acknowledged === "1" ? " is" : "s are"} acknowledged.`);
    return parts.join(" ");
  }

  if (upper.includes("SERVICE") && upper.includes("VERIFIED")) {
    const healthy = firstMatch(normalized, /Healthy:\s*(\d+\/\d+)/i);
    const reachable = firstMatch(normalized, /Reachable:\s*(\d+\/\d+|\d+)/i);
    const unreachable = firstMatch(normalized, /Unreachable:\s*(\d+)/i);
    const parts = ["Service status is verified."];
    if (healthy) parts.push(`${healthy} monitored services are healthy.`);
    else if (reachable) parts.push(`${reachable} monitored services are reachable.`);
    if (unreachable && Number(unreachable) > 0) {
      parts.push(`${unreachable} service${unreachable === "1" ? " is" : "s are"} unreachable.`);
    }
    return parts.join(" ");
  }

  if (upper.includes("MEMORY") && upper.includes("VERIFIED")) {
    const usage = firstMatch(normalized, /Memory usage:\s*([0-9.]+%)/i);
    const used = firstMatch(normalized, /Memory used:\s*([^|]+?)(?=\s+Memory available:|\s+Memory total:|$)/i);
    const available = firstMatch(normalized, /Memory available:\s*([^|]+?)(?=\s+Memory total:|$)/i);
    const parts = ["Memory status is verified."];
    if (usage) parts.push(`Memory utilization is ${usage}.`);
    if (used && available) parts.push(`${used} is in use with ${available} available.`);
    return parts.join(" ");
  }

  return normalized;
}

export async function getVoiceStatus(): Promise<VoiceStatus> {
  const response = await fetch("/api/voice/status");
  if (!response.ok) {
    throw new Error(`Voice status returned ${response.status}`);
  }
  return response.json();
}

export async function getSttStatus(): Promise<SttStatus> {
  const response = await fetch("/api/voice/stt/status");
  if (!response.ok) {
    throw new Error(`STT status returned ${response.status}`);
  }
  return response.json();
}

export async function transcribeAudio(
  audio: Blob,
  filename = "microphone.webm",
): Promise<TranscriptionResult> {
  const form = new FormData();
  form.append("file", audio, filename);

  const response = await fetch("/api/voice/transcribe", {
    method: "POST",
    body: form,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`STT transcription returned ${response.status}: ${detail}`);
  }

  return response.json();
}

export async function synthesizeSpeech(
  text: string,
  voice?: string,
): Promise<Blob> {
  const speechText = toolAwareSpeechText(text);

  const response = await fetch("/api/voice/speech", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: speechText, voice }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Voice synthesis returned ${response.status}: ${detail}`);
  }

  return response.blob();
}
