import type { AgentSpec } from "../types";

interface Props {
  agent: AgentSpec | undefined;
  agentId: string;
  coord: string;
  move: number;
  confidence: number;
  message: string;
  onHover: (cell: number | null) => void;
}

export function AgentMessageBubble({
  agent,
  agentId,
  coord,
  move,
  confidence,
  message,
  onHover,
}: Props) {
  const color = agent?.color ?? "#64748b";
  return (
    <div
      className="flex gap-2"
      onMouseEnter={() => onHover(move)}
      onMouseLeave={() => onHover(null)}
      data-testid="agent-message"
    >
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-lg"
        style={{ backgroundColor: `${color}22`, border: `2px solid ${color}` }}
        aria-hidden
      >
        {agent?.avatar ?? "🤖"}
      </div>
      <div
        className="min-w-0 flex-1 rounded-lg bg-white p-2 shadow-sm"
        style={{ borderLeft: `4px solid ${color}` }}
      >
        <div className="flex flex-wrap items-center gap-x-2 text-xs">
          <span className="font-bold" style={{ color }}>
            {agent?.name ?? agentId}
          </span>
          <span className="text-slate-500">{agent?.personality}</span>
        </div>
        <p className="mt-1 break-words text-sm">{message}</p>
        <div className="mt-1 flex gap-2 text-xs">
          <span className="rounded-full bg-slate-900 px-2 py-0.5 font-semibold text-white">
            Propone {coord}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-slate-600">
            Confianza {Math.round(confidence * 100)}%
          </span>
        </div>
      </div>
    </div>
  );
}
