import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Board } from "./Board";
import type { Cell } from "../types";

function renderBoard(size: number, overrides: Partial<Parameters<typeof Board>[0]> = {}) {
  const onCellClick = vi.fn();
  const board: Cell[] = Array(size * size).fill(null);
  render(
    <Board
      boardSize={size}
      board={board}
      disabled={false}
      lastMoves={{ human: null, machine: null }}
      winningLine={[]}
      highlightedCell={null}
      onCellClick={onCellClick}
      {...overrides}
    />,
  );
  return { onCellClick, board };
}

describe("Board", () => {
  it.each([3, 4, 6, 8])("renderiza board_size² celdas para %i", (size) => {
    renderBoard(size);
    expect(screen.getAllByRole("button")).toHaveLength(size * size);
  });

  it("muestra rótulos de columnas A-F y filas 1-6", () => {
    renderBoard(6);
    for (const label of ["A", "B", "C", "D", "E", "F", "1", "2", "3", "4", "5", "6"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    expect(screen.queryByText("G")).not.toBeInTheDocument();
  });

  it("los rótulos se adaptan al tamaño recibido", () => {
    renderBoard(4);
    expect(screen.getByText("D")).toBeInTheDocument();
    expect(screen.queryByText("E")).not.toBeInTheDocument();
  });

  it("dispara el click con el índice (fila * size + columna)", async () => {
    const { onCellClick } = renderBoard(6);
    await userEvent.click(screen.getByLabelText("Celda C3, vacía"));
    expect(onCellClick).toHaveBeenCalledWith(14);
  });

  it("no permite clicks cuando está deshabilitado", async () => {
    const { onCellClick } = renderBoard(6, { disabled: true });
    await userEvent.click(screen.getByTestId("cell-0"));
    expect(onCellClick).not.toHaveBeenCalled();
  });

  it("no permite jugar en una celda ocupada", async () => {
    const board: Cell[] = Array(36).fill(null);
    board[0] = "X";
    const { onCellClick } = renderBoard(6, { board });
    expect(screen.getByLabelText("Celda A1, tuya (X)")).toBeDisabled();
    await userEvent.click(screen.getByTestId("cell-0"));
    expect(onCellClick).not.toHaveBeenCalled();
  });

  it("resalta la línea ganadora", () => {
    renderBoard(6, { winningLine: [0, 1, 2, 3] });
    expect(screen.getByTestId("cell-1").className).toContain("emerald");
    expect(screen.getByTestId("cell-4").className).not.toContain("emerald");
  });

  it("resalta la celda señalada desde el chat", () => {
    renderBoard(6, { highlightedCell: 20 });
    expect(screen.getByTestId("cell-20").className).toContain("amber");
  });
});
