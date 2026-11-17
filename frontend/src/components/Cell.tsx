import type { Cell as CellValue } from "../types";

interface Props {
  index: number;
  coord: string;
  value: CellValue;
  disabled: boolean;
  isLastHuman: boolean;
  isLastMachine: boolean;
  isWinning: boolean;
  isHighlighted: boolean;
  onClick: (index: number) => void;
}

export function Cell({
  index,
  coord,
  value,
  disabled,
  isLastHuman,
  isLastMachine,
  isWinning,
  isHighlighted,
  onClick,
}: Props) {
  const clickable = !disabled && value === null;
  const ring = isWinning
    ? "bg-emerald-200 ring-2 ring-emerald-500"
    : isHighlighted
      ? "bg-amber-100 ring-2 ring-amber-500"
      : isLastHuman
        ? "bg-sky-50 ring-2 ring-sky-300"
        : isLastMachine
          ? "bg-rose-50 ring-2 ring-rose-300"
          : "bg-white";
  const label = `Celda ${coord}, ${value === "X" ? "tuya (X)" : value === "O" ? "de la máquina (O)" : "vacía"}`;
  return (
    <button
      type="button"
      aria-label={label}
      data-testid={`cell-${index}`}
      disabled={!clickable}
      onClick={() => onClick(index)}
      className={`flex aspect-square min-h-9 items-center justify-center rounded-md border border-slate-300 text-lg font-bold transition sm:text-2xl ${ring} ${
        clickable ? "cursor-pointer hover:bg-slate-100" : "cursor-default"
      } ${value === "X" ? "text-sky-700" : "text-rose-600"}`}
    >
      {value}
    </button>
  );
}
