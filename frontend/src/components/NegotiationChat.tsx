import { useEffect, useRef } from "react";
import type { AgentSpec, ChatItem } from "../types";
import { AgentMessageBubble } from "./AgentMessageBubble";
import { DecisionBanner } from "./DecisionBanner";

interface Props {
  items: ChatItem[];
  agents: AgentSpec[];
  thinkingAgentId: string | null;
  onHoverCell: (cell: number | null) => void;
}

export function NegotiationChat({ items, agents, thinkingAgentId, onHoverCell }: Props) {
  const byId = new Map(agents.map((a) => [a.id, a]));
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [items.length, thinkingAgentId]);

  const thinking = thinkingAgentId ? byId.get(thinkingAgentId) : undefined;

  return (
    <div
      ref={box}
      aria-label="Chat de negociación"
      className="flex h-80 flex-col gap-2 overflow-y-auto rounded-lg bg-slate-50 p-3 lg:h-[34rem]"
    >
      {items.length === 0 && !thinking && (
        <p className="m-auto text-center text-sm text-slate-500">
          Haz tu jugada: aquí verás cómo negocian los agentes la respuesta de la máquina.
        </p>
      )}
      {items.map((item) => {
        switch (item.kind) {
          case "turn":
            return (
              <div key={item.id} className="mt-2 border-b border-slate-300 pb-1 text-xs font-bold uppercase text-slate-500">
                Turno de la máquina #{item.turn}
              </div>
            );
          case "round":
            return (
              <div key={item.id} className="text-center text-xs font-semibold text-slate-400">
                — Ronda {item.round} —
              </div>
            );
          case "message":
            return (
              <AgentMessageBubble
                key={item.id}
                agent={byId.get(item.agentId)}
                agentId={item.agentId}
                coord={item.coord}
                move={item.move}
                confidence={item.confidence}
                message={item.message}
                onHover={onHoverCell}
              />
            );
          case "error":
            return (
              <div key={item.id} role="alert" className="rounded-lg bg-rose-50 px-3 py-1.5 text-xs text-rose-800">
                ⚠️ {byId.get(item.agentId)?.name ?? item.agentId}: intervención inválida, no cuenta
                como voto. ({item.reason})
              </div>
            );
          case "decision":
            return <DecisionBanner key={item.id} item={item} />;
        }
      })}
      {thinking && (
        <div className="flex items-center gap-2 text-sm text-slate-500" data-testid="typing">
          <span aria-hidden>{thinking.avatar}</span>
          <span>{thinking.name} está escribiendo…</span>
        </div>
      )}
    </div>
  );
}
