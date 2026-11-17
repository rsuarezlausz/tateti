import type { GameSnapshot, MetricsSummary, SSEEvent } from "../types";
import { createSSEParser } from "./sse";

export const API_URL: string = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function failure(res: Response): Promise<ApiError> {
  let detail = `Error ${res.status}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detail = body.detail;
    else if (body.detail) detail = "Solicitud inválida";
  } catch {
    /* sin cuerpo JSON */
  }
  return new ApiError(res.status, detail);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, init);
  } catch {
    throw new ApiError(0, "No se pudo conectar con el servidor");
  }
  if (!res.ok) throw await failure(res);
  return res.json() as Promise<T>;
}

export type StartingPlayer = "human" | "machine";

export function createGame(
  numAgents: number,
  startingPlayer: StartingPlayer = "human",
): Promise<GameSnapshot> {
  return request("/api/games", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ num_agents: numAgents, starting_player: startingPlayer }),
  });
}
export function getGame(gameId: string): Promise<GameSnapshot> {
  return request(`/api/games/${gameId}`);
}

export function getMetrics(gameId: string): Promise<MetricsSummary> {
  return request(`/api/games/${gameId}/metrics`);
}

/** Consume un SSE por POST con fetch + ReadableStream (no EventSource). */
async function* streamPost(
  path: string,
  body: object | undefined,
  signal?: AbortSignal,
): AsyncGenerator<SSEEvent> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "No se pudo conectar con el servidor");
  }
  if (!res.ok) throw await failure(res);
  if (!res.body) throw new ApiError(0, "El servidor no devolvió un stream");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  const parser = createSSEParser();
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      yield* parser.feed(decoder.decode(value, { stream: true }));
    }
    yield* parser.feed(decoder.decode() + "\n\n");
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "Se interrumpió la conexión con el servidor");
  } finally {
    reader.releaseLock();
  }
}

/** Jugada humana: POST /move. */
export function streamMove(gameId: string, cell: number, signal?: AbortSignal) {
  return streamPost(`/api/games/${gameId}/move`, { cell }, signal);
}

/** Apertura de la máquina (cuando empieza ella): POST /start. */
export function streamStart(gameId: string, signal?: AbortSignal) {
  return streamPost(`/api/games/${gameId}/start`, undefined, signal);
}