export type Player = "X" | "O";
export type Cell = Player | null;
export type GameStatusValue = "in_progress" | "human_won" | "machine_won" | "draw";

export interface AgentSpec {
  id: string;
  name: string;
  personality: string;
  skills: string[];
  system_prompt: string;
  temperature: number;
  color: string;
  avatar: string;
}

export interface GameSnapshot {
  game_id: string;
  board_size: number;
  win_length: number;
  board: Cell[];
  status: GameStatusValue;
  turn: "human" | "machine" | null;
  starting_player: "human" | "machine";
  winning_line: number[];
  last_moves: { human: number | null; machine: number | null };
  agents: AgentSpec[];
}

export interface UsageTotals {
  calls: number;
  failed_calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_latency_ms: number;
  avg_latency_ms: number;
  total_cost: number | null;
}

export interface AgentMetrics extends UsageTotals {
  agent_id: string;
}

export interface MetricsSummary {
  agents: AgentMetrics[];
  total: UsageTotals;
}

export interface SSEEvent {
  name: string;
  data: Record<string, any>;
}

export type ChatItem =
  | { kind: "turn"; id: string; turn: number }
  | { kind: "round"; id: string; round: number }
  | {
      kind: "message";
      id: string;
      round: number;
      agentId: string;
      message: string;
      move: number;
      coord: string;
      confidence: number;
    }
  | { kind: "error"; id: string; round: number; agentId: string; reason: string }
  | {
      kind: "decision";
      id: string;
      decision: "consensus" | "tiebreak" | "fallback";
      move: number;
      coord: string;
      round?: number;
      candidateCoords?: string[];
      drawn?: boolean;
      reason?: string;
    };
