import { gameReducer, initialState, type Action, type GameState } from "./gameReducer";
import type { GameSnapshot, SSEEvent } from "../types";

const snapshot: GameSnapshot = {
  game_id: "g1",
  board_size: 6,
  win_length: 4,
  board: Array(36).fill(null),
  status: "in_progress",
  turn: "human",
  starting_player: "human",
  winning_line: [],
  last_moves: { human: null, machine: null },
  agents: [
    { id: "a", name: "A", personality: "p", skills: [], system_prompt: "", temperature: 0.5, color: "#000000", avatar: "🧠" },
    { id: "b", name: "B", personality: "p", skills: [], system_prompt: "", temperature: 0.5, color: "#111111", avatar: "🛡️" },
  ],
};

const ev = (name: string, data: object = {}): Action => ({ type: "EVENT", event: { name, data } as SSEEvent });
const run = (actions: Action[], from: GameState = initialState) => actions.reduce(gameReducer, from);
const loaded = () => run([{ type: "GAME_LOADED", game: snapshot, reset: true }]);

const msg = (agent: string, round: number, move = 0) =>
  ev("agent_message", { round, agent_id: agent, message: "hola", proposed_move: move, coord: "A1", confidence: 0.5 });

describe("gameReducer", () => {
  it("carga la partida con el board_size recibido", () => {
    const s = loaded();
    expect(s.boardSize).toBe(6);
    expect(s.board).toHaveLength(36);
    expect(s.agents).toHaveLength(2);
    expect(s.chat).toEqual([]);
  });

  it("bloquea el tablero al jugar y lo libera al terminar", () => {
    const s = run([{ type: "MOVE_STARTED" }], loaded());
    expect(s.busy).toBe(true);
    expect(gameReducer(s, { type: "MOVE_FINISHED" }).busy).toBe(false);
  });

  it("human_move y machine_move actualizan tablero y últimas jugadas", () => {
    const board = Array(36).fill(null);
    board[14] = "X";
    let s = run([ev("human_move", { cell: 14, board })], loaded());
    expect(s.board[14]).toBe("X");
    expect(s.lastMoves.human).toBe(14);
    board[0] = "O";
    s = run([ev("machine_move", { cell: 0, board })], s);
    expect(s.lastMoves).toEqual({ human: 14, machine: 0 });
  });

  it("agrega separadores, burbujas y decisión al chat en orden", () => {
    const s = run(
      [
        ev("negotiation_started", { max_rounds: 3, agents: ["a", "b"] }),
        ev("round_started", { round: 1 }),
        msg("a", 1),
        msg("b", 1),
        ev("consensus", { move: 0, coord: "A1", round: 1 }),
      ],
      loaded(),
    );
    expect(s.chat.map((c) => c.kind)).toEqual(["turn", "round", "message", "message", "decision"]);
    expect(s.thinkingAgentId).toBeNull();
  });

  it("marca quién está escribiendo según el orden secuencial", () => {
    let s = run(
      [ev("negotiation_started", { agents: ["a", "b"] }), ev("round_started", { round: 1 })],
      loaded(),
    );
    expect(s.thinkingAgentId).toBe("a");
    s = run([msg("a", 1)], s);
    expect(s.thinkingAgentId).toBe("b");
    s = run([ev("agent_error", { round: 1, agent_id: "b", reason: "x" })], s);
    expect(s.thinkingAgentId).toBeNull();
    s = run([ev("round_started", { round: 2 })], s);
    expect(s.thinkingAgentId).toBe("a");
  });

  it("guarda los datos del sorteo y del fallback", () => {
    const s = run(
      [
        ev("tiebreak", { move: 1, coord: "B1", candidate_coords: ["A1", "B1"], drawn: true }),
        ev("fallback", { move: 2, coord: "C1", reason: "azar" }),
      ],
      loaded(),
    );
    expect(s.chat[0]).toMatchObject({ decision: "tiebreak", drawn: true, candidateCoords: ["A1", "B1"] });
    expect(s.chat[1]).toMatchObject({ decision: "fallback", reason: "azar" });
  });

  it("metrics_update guarda el resumen", () => {
    const metrics = { agents: [], total: { calls: 3 } };
    expect(run([ev("metrics_update", metrics)], loaded()).metrics).toEqual(metrics);
  });

  it("game_over fija estado y línea ganadora y libera el tablero", () => {
    const s = run(
      [{ type: "MOVE_STARTED" }, ev("game_over", { status: "human_won", line: [0, 1, 2, 3] })],
      loaded(),
    );
    expect(s).toMatchObject({ status: "human_won", winningLine: [0, 1, 2, 3], busy: false });
  });

  it("el evento error y FAILED muestran el mensaje y liberan el tablero", () => {
    let s = run([{ type: "MOVE_STARTED" }, ev("error", { detail: "falló" })], loaded());
    expect(s.error).toBe("falló");
    s = run([{ type: "MOVE_STARTED" }, { type: "FAILED", message: "sin red" }], loaded());
    expect(s).toMatchObject({ error: "sin red", busy: false });
  });

  it("una partida nueva reinicia chat y errores", () => {
    const dirty = run([ev("round_started", { round: 1 }), { type: "FAILED", message: "x" }], loaded());
    const s = run([{ type: "GAME_LOADED", game: snapshot, reset: true }], dirty);
    expect(s.chat).toEqual([]);
    expect(s.error).toBeNull();
  });

  it("ignora eventos desconocidos", () => {
    const s = loaded();
    expect(run([ev("otro")], s)).toBe(s);
  });
});
