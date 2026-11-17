import type {
  AgentSpec,
  Cell,
  ChatItem,
  GameSnapshot,
  GameStatusValue,
  MetricsSummary,
  SSEEvent,
} from "../types";

export interface GameState {
  gameId: string | null;
  boardSize: number;
  winLength: number;
  board: Cell[];
  status: GameStatusValue;
  /** a quién le toca según el backend (null si terminó) */
  turn: "human" | "machine" | null;
  winningLine: number[];
  lastMoves: { human: number | null; machine: number | null };
  agents: AgentSpec[];
  /** true mientras la máquina negocia (el tablero se bloquea) */
  busy: boolean;
  chat: ChatItem[];
  /** agentes de la negociación en curso, en orden de intervención */
  order: string[];
  position: number;
  thinkingAgentId: string | null;
  turnCount: number;
  metrics: MetricsSummary | null;
  loading: boolean;
  error: string | null;
}

export const initialState: GameState = {
  gameId: null,
  boardSize: 0,
  winLength: 0,
  board: [],
  status: "in_progress",
  turn: null,
  winningLine: [],
  lastMoves: { human: null, machine: null },
  agents: [],
  busy: false,
  chat: [],
  order: [],
  position: 0,
  thinkingAgentId: null,
  turnCount: 0,
  metrics: null,
  loading: false,
  error: null,
};

export type Action =
  | { type: "LOADING" }
  | { type: "GAME_LOADED"; game: GameSnapshot; reset?: boolean }
  | { type: "MOVE_STARTED" }
  | { type: "MOVE_FINISHED" }
  | { type: "FAILED"; message: string }
  | { type: "EVENT"; event: SSEEvent };

function snapshotFields(game: GameSnapshot) {
  return {
    gameId: game.game_id,
    boardSize: game.board_size,
    winLength: game.win_length,
    board: game.board,
    status: game.status,
    turn: game.turn,
    winningLine: game.winning_line,
    lastMoves: game.last_moves,
    agents: game.agents,
  };
}

function afterSpeaker(state: GameState, chat: ChatItem[]): GameState {
  const position = state.position + 1;
  return {
    ...state,
    chat,
    position,
    thinkingAgentId: state.order[position] ?? null,
  };
}

function itemId(state: GameState, suffix: string): string {
  return `${state.chat.length}-${suffix}`;
}

export function gameReducer(state: GameState, action: Action): GameState {
  switch (action.type) {
    case "LOADING":
      return { ...state, loading: true, error: null };
    case "GAME_LOADED":
      if (action.reset) {
        return { ...initialState, ...snapshotFields(action.game) };
      }
      return { ...state, ...snapshotFields(action.game), loading: false };
    case "MOVE_STARTED":
      return { ...state, busy: true, error: null, thinkingAgentId: null, order: [], position: 0 };
    case "MOVE_FINISHED":
      return { ...state, busy: false, thinkingAgentId: null };
    case "FAILED":
      return { ...state, loading: false, busy: false, thinkingAgentId: null, error: action.message };
    case "EVENT":
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: GameState, { name, data }: SSEEvent): GameState {
  switch (name) {
    case "human_move":
      return {
        ...state,
        board: data.board,
        lastMoves: { ...state.lastMoves, human: data.cell },
      };
    case "negotiation_started": {
      const turn = state.turnCount + 1;
      return {
        ...state,
        turnCount: turn,
        order: data.agents,
        position: 0,
        chat: [...state.chat, { kind: "turn", id: itemId(state, "turn"), turn }],
      };
    }
    case "round_started":
      return {
        ...state,
        position: 0,
        thinkingAgentId: state.order[0] ?? null,
        chat: [
          ...state.chat,
          { kind: "round", id: itemId(state, "round"), round: data.round },
        ],
      };
    case "agent_message":
      return afterSpeaker(state, [
        ...state.chat,
        {
          kind: "message",
          id: itemId(state, "msg"),
          round: data.round,
          agentId: data.agent_id,
          message: data.message,
          move: data.proposed_move,
          coord: data.coord,
          confidence: data.confidence,
        },
      ]);
    case "agent_error":
      return afterSpeaker(state, [
        ...state.chat,
        {
          kind: "error",
          id: itemId(state, "err"),
          round: data.round,
          agentId: data.agent_id,
          reason: data.reason,
        },
      ]);
    case "consensus":
    case "tiebreak":
    case "fallback":
      return {
        ...state,
        thinkingAgentId: null,
        chat: [
          ...state.chat,
          {
            kind: "decision",
            id: itemId(state, "decision"),
            decision: name,
            move: data.move,
            coord: data.coord,
            round: data.round,
            candidateCoords: data.candidate_coords,
            drawn: data.drawn,
            reason: data.reason,
          },
        ],
      };
    case "machine_move":
      return {
        ...state,
        board: data.board,
        lastMoves: { ...state.lastMoves, machine: data.cell },
      };
    case "metrics_update":
      return { ...state, metrics: data as MetricsSummary };
    case "game_over":
      return {
        ...state,
        status: data.status,
        winningLine: data.line,
        busy: false,
        thinkingAgentId: null,
      };
    case "error":
      return { ...state, error: data.detail ?? "Error inesperado", thinkingAgentId: null };
    default:
      return state;
  }
}
