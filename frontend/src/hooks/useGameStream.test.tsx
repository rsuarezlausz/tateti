import { act, renderHook, waitFor } from "@testing-library/react";
import { useGameStream } from "./useGameStream";
import type { GameSnapshot } from "../types";

const agents = [
  { id: "a", name: "A", personality: "p", skills: [], system_prompt: "", temperature: 0.5, color: "#000000", avatar: "🧠" },
];

function snapshot(over: Partial<GameSnapshot> = {}): GameSnapshot {
  return {
    game_id: "g1",
    board_size: 3,
    win_length: 3,
    board: Array(9).fill(null),
    status: "in_progress",
    turn: "human",
    starting_player: "human",
    winning_line: [],
    last_moves: { human: null, machine: null },
    agents,
    ...over,
  };
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

function sseResponse(events: [string, object][]) {
  const text = events.map(([n, d]) => `event: ${n}\ndata: ${JSON.stringify(d)}\n\n`).join("");
  return new Response(text, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

const OPENING = [
  ["negotiation_started", { max_rounds: 3, agents: ["a"] }],
  ["round_started", { round: 1 }],
  ["agent_message", { round: 1, agent_id: "a", message: "abro", proposed_move: 4, coord: "B2", confidence: 0.9 }],
  ["consensus", { move: 4, coord: "B2", round: 1 }],
  ["machine_move", { cell: 4, coord: "B2", board: [null, null, null, null, "O", null, null, null, null] }],
] as [string, object][];

afterEach(() => vi.unstubAllGlobals());

function mockFetch(routes: Record<string, () => Response>) {
  const calls: { url: string; method: string; body?: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const path = url.replace(/^https?:\/\/[^/]+/, "");
      const method = init?.method ?? "GET";
      calls.push({ url: path, method, body: init?.body as string | undefined });
      const route = routes[`${method} ${path}`];
      if (!route) throw new Error(`ruta no mockeada: ${method} ${path}`);
      return route();
    }),
  );
  return calls;
}

describe("useGameStream: quién empieza", () => {
  it("si empieza el humano no pide la apertura de la máquina", async () => {
    const calls = mockFetch({ "POST /api/games": () => json(snapshot(), 201) });
    const { result } = renderHook(() => useGameStream());
    await act(() => result.current.startGame(2, "human"));
    expect(JSON.parse(calls[0].body!)).toEqual({ num_agents: 2, starting_player: "human" });
    expect(calls.map((c) => c.url)).toEqual(["/api/games"]);
    expect(result.current.state.busy).toBe(false);
  });

  it("si empieza la máquina pide /start, muestra la negociación y devuelve el turno al humano", async () => {
    const afterOpening = snapshot({
      board: [null, null, null, null, "O", null, null, null, null],
      starting_player: "machine",
      last_moves: { human: null, machine: 4 },
    });
    const calls = mockFetch({
      "POST /api/games": () => json(snapshot({ starting_player: "machine", turn: "machine" }), 201),
      "POST /api/games/g1/start": () => sseResponse(OPENING),
      "GET /api/games/g1": () => json(afterOpening),
    });
    const { result } = renderHook(() => useGameStream());
    await act(() => result.current.startGame(1, "machine"));
    await waitFor(() => expect(result.current.state.busy).toBe(false));
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      "POST /api/games",
      "POST /api/games/g1/start",
      "GET /api/games/g1",
    ]);
    const { state } = result.current;
    expect(state.board[4]).toBe("O");
    expect(state.turn).toBe("human");
    expect(state.chat.map((c) => c.kind)).toEqual(["turn", "round", "message", "decision"]);
  });

  it("no deja jugar al humano mientras es el turno de la máquina", async () => {
    const calls = mockFetch({
      "POST /api/games": () => json(snapshot({ starting_player: "machine", turn: "machine" }), 201),
      "POST /api/games/g1/start": () => json({ detail: "fallo" }, 500),
      "GET /api/games/g1": () => json(snapshot({ starting_player: "machine", turn: "machine" })),
    });
    const { result } = renderHook(() => useGameStream());
    await act(() => result.current.startGame(1, "machine"));
    await waitFor(() => expect(result.current.state.busy).toBe(false));
    expect(result.current.state.error).toBeTruthy();
    const before = calls.length;
    act(() => result.current.play(0));
    expect(calls.length).toBe(before); // no se envió ningún /move
  });

  it("reintentar tras un fallo repite la apertura de la máquina (no un move)", async () => {
    let attempt = 0;
    const calls = mockFetch({
      "POST /api/games": () => json(snapshot({ starting_player: "machine", turn: "machine" }), 201),
      "POST /api/games/g1/start": () => (++attempt === 1 ? json({ detail: "x" }, 500) : sseResponse(OPENING)),
      "GET /api/games/g1": () =>
        json(snapshot({ starting_player: "machine", turn: attempt === 1 ? "machine" : "human" })),
    });
    const { result } = renderHook(() => useGameStream());
    await act(() => result.current.startGame(1, "machine"));
    await waitFor(() => expect(result.current.state.busy).toBe(false));
    await act(async () => result.current.retry());
    await waitFor(() => expect(result.current.state.busy).toBe(false));
    const starts = calls.filter((c) => c.url.endsWith("/start"));
    expect(starts).toHaveLength(2);
    expect(calls.some((c) => c.url.endsWith("/move"))).toBe(false);
    expect(result.current.state.turn).toBe("human");
  });
});
