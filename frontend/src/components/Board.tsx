import { columnLabels, indexToCoord } from "../lib/coords";
import type { Cell as CellValue } from "../types";
import { Cell } from "./Cell";

interface Props {
  boardSize: number;
  board: CellValue[];
  disabled: boolean;
  lastMoves: { human: number | null; machine: number | null };
  winningLine: number[];
  highlightedCell: number | null;
  onCellClick: (index: number) => void;
}

/** Tablero dinámico: el tamaño sale de `boardSize` (nunca fijo). */
export function Board({
  boardSize,
  board,
  disabled,
  lastMoves,
  winningLine,
  highlightedCell,
  onCellClick,
}: Props) {
  const columns = columnLabels(boardSize);
  const rows = Array.from({ length: boardSize }, (_, r) => r);
  return (
    <div
      role="grid"
      aria-label="Tablero"
      className="mx-auto grid w-full max-w-xl select-none gap-1"
      style={{ gridTemplateColumns: `1.25rem repeat(${boardSize}, minmax(0, 1fr))` }}
    >
      <div />
      {columns.map((c) => (
        <div key={c} className="text-center text-xs font-semibold text-slate-500">
          {c}
        </div>
      ))}
      {rows.map((r) => (
        <div key={r} className="contents">
          <div className="flex items-center justify-center text-xs font-semibold text-slate-500">
            {r + 1}
          </div>
          {columns.map((_, c) => {
            const index = r * boardSize + c;
            return (
              <Cell
                key={index}
                index={index}
                coord={indexToCoord(index, boardSize)}
                value={board[index] ?? null}
                disabled={disabled}
                isLastHuman={lastMoves.human === index}
                isLastMachine={lastMoves.machine === index}
                isWinning={winningLine.includes(index)}
                isHighlighted={highlightedCell === index}
                onClick={onCellClick}
              />
            );
          })}
        </div>
      ))}
    </div>
  );
}
