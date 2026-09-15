export type ModelState = {
  provider: string;
  default_model: string;
  active_model: string;
  available_models: string[];
};

async function modelResponse(response: Response): Promise<ModelState> {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`Model control returned ${response.status}: ${detail}`);
  }
  return response.json();
}

export async function getModelState(): Promise<ModelState> {
  return modelResponse(await fetch("/api/models/state"));
}

export async function setActiveModel(model: string): Promise<ModelState> {
  return modelResponse(
    await fetch("/api/models/active", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ model }),
    }),
  );
}
