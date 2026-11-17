import type { ChatItem } from "../types";

type Decision = Extract<ChatItem, { kind: "decision" }>;

export function decisionText(d: Decision): string {
  if (d.decision === "consensus") {
    return `Consenso en la ronda ${d.round}: la máquina juega ${d.coord}.`;
  }
  if (d.decision === "tiebreak") {
    return d.drawn
      ? `Sin consenso: sorteo entre las jugadas más votadas (${d.candidateCoords?.join(", ")}). Salió ${d.coord}.`
      : `Sin consenso: se impuso la jugada más votada, ${d.coord}.`;
  }
  return `${d.reason ?? "Ningún agente aportó un voto válido."} La máquina juega ${d.coord}.`;
}

export function DecisionBanner({ item }: { item: Decision }) {
  const tone =
    item.decision === "consensus"
      ? "bg-emerald-100 text-emerald-900"
      : item.decision === "tiebreak"
        ? "bg-amber-100 text-amber-900"
        : "bg-rose-100 text-rose-900";
  return (
    <div role="note" className={`rounded-lg px-3 py-2 text-sm font-semibold ${tone}`}>
      {decisionText(item)}
    </div>
  );
}
