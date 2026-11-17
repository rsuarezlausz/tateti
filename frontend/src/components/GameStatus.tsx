import type { GameStatusValue } from "../types";

interface Props {
  status: GameStatusValue;
  busy: boolean;
  loading: boolean;
  hasGame: boolean;
}

export function GameStatus({ status, busy, loading, hasGame }: Props) {
  let text = "Elige la cantidad de agentes y pulsa «Nueva partida»";
  let tone = "bg-slate-200 text-slate-700";
  if (loading) text = "Creando partida…";
  else if (hasGame) {
    if (status === "human_won") [text, tone] = ["¡Ganaste!", "bg-emerald-100 text-emerald-800"];
    else if (status === "machine_won") [text, tone] = ["Perdiste", "bg-rose-100 text-rose-800"];
    else if (status === "draw") [text, tone] = ["Empate", "bg-amber-100 text-amber-800"];
    else if (busy) [text, tone] = ["La máquina está negociando…", "bg-violet-100 text-violet-800"];
    else [text, tone] = ["Tu turno (X)", "bg-sky-100 text-sky-800"];
  }
  return (
    <p role="status" className={`rounded-lg px-3 py-2 text-center font-semibold ${tone}`}>
      {text}
    </p>
  );
}
