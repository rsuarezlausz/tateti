import type { StartingPlayer } from "../api/client";

export const MIN_AGENTS = 1;
export const MAX_AGENTS = 4;

interface Props {
  value: number;
  disabled: boolean;
  onChange: (n: number) => void;
  startingPlayer: StartingPlayer;
  onStartingPlayerChange: (p: StartingPlayer) => void;
  onNewGame: () => void;
}

export function AgentCountSelector({
  value,
  disabled,
  onChange,
  startingPlayer,
  onStartingPlayerChange,
  onNewGame,
}: Props) {
  const options = Array.from({ length: MAX_AGENTS - MIN_AGENTS + 1 }, (_, i) => MIN_AGENTS + i);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <label className="flex items-center gap-2 text-sm font-medium">
        Agentes
        <select
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(Number(e.target.value))}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          {options.map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <label className="flex items-center gap-2 text-sm font-medium">
        Empieza
        <select
          value={startingPlayer}
          disabled={disabled}
          onChange={(e) => onStartingPlayerChange(e.target.value as StartingPlayer)}
          className="rounded-md border border-slate-300 bg-white px-2 py-1"
        >
          <option value="human">Humano</option>
          <option value="machine">Máquina</option>
        </select>
      </label>
      <button
        type="button"
        disabled={disabled}
        onClick={onNewGame}
        className="rounded-md bg-slate-900 px-4 py-1.5 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
      >
        Nueva partida
      </button>
    </div>
  );
}
