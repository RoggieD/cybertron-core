export type VoiceStatus = {
  provider: string;
  base_url: string;
  default_voice: string;
  reachable: boolean;
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
