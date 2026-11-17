import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AgentCountSelector } from "./AgentCountSelector";

function setup(overrides = {}) {
  const props = {
    value: 3,
    disabled: false,
    onChange: vi.fn(),
    startingPlayer: "human" as const,
    onStartingPlayerChange: vi.fn(),
    onNewGame: vi.fn(),
    ...overrides,
  };
  render(<AgentCountSelector {...props} />);
  return props;
}

describe("AgentCountSelector", () => {
  it("permite elegir entre 1 y 4 agentes", async () => {
    const p = setup();
    const select = screen.getByLabelText("Agentes");
    expect(screen.getAllByRole("option", { name: /^[1-4]$/ })).toHaveLength(4);
    await userEvent.selectOptions(select, "4");
    expect(p.onChange).toHaveBeenCalledWith(4);
  });

  it("permite elegir quién empieza", async () => {
    const p = setup();
    expect(screen.getByLabelText("Empieza")).toHaveValue("human");
    await userEvent.selectOptions(screen.getByLabelText("Empieza"), "machine");
    expect(p.onStartingPlayerChange).toHaveBeenCalledWith("machine");
  });

  it("refleja el valor actual y bloquea todo mientras la máquina negocia", () => {
    setup({ startingPlayer: "machine", disabled: true });
    expect(screen.getByLabelText("Empieza")).toHaveValue("machine");
    expect(screen.getByLabelText("Empieza")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Nueva partida" })).toBeDisabled();
  });

  it("Nueva partida dispara el callback", async () => {
    const p = setup();
    await userEvent.click(screen.getByRole("button", { name: "Nueva partida" }));
    expect(p.onNewGame).toHaveBeenCalled();
  });
});
