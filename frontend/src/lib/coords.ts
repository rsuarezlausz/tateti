const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

export function columnLabels(boardSize: number): string[] {
  return LETTERS.slice(0, boardSize).split("");
}

/** Índice (`fila * boardSize + columna`) -> coordenada humana (C3). */
export function indexToCoord(index: number, boardSize: number): string {
  const row = Math.floor(index / boardSize);
  const col = index % boardSize;
  return `${LETTERS[col]}${row + 1}`;
}
