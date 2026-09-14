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

function apiBase(): string {
  return `http://${window.location.hostname}:8000`;
}

export async function getVoiceStatus(): Promise<VoiceStatus> {
  const response = await fetch(`${apiBase()}/api/voice/status`);
  if (!response.ok) {
    throw new Error(`Voice status returned ${response.status}`);
  }
  return response.json();
}

export async function getSttStatus(): Promise<SttStatus> {
  const response = await fetch(`${apiBase()}/api/voice/stt/status`);
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

  const response = await fetch(`${apiBase()}/api/voice/transcribe`, {
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
  const response = await fetch(`${apiBase()}/api/voice/speech`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, voice }),
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Voice synthesis returned ${response.status}: ${detail}`);
  }

  return response.blob();
}
