import { useCallback, useEffect, useReducer, useRef } from "react";
import {
  ApiError,
  createGame,
  getGame,
  streamMove,
  streamStart,
  type StartingPlayer,
} from "../api/client";
import { gameReducer, initialState } from "../state/gameReducer";

function messageOf(e: unknown): string {
  if (e instanceof ApiError && e.status === 404) {
    return "La partida ya no existe (el servidor se reinició). Pulsa «Nueva partida».";
  }
  return e instanceof ApiError ? e.message : "Ocurrió un error inesperado";
}

type StreamAction = { kind: "move"; cell: number } | { kind: "start" };

/** Encapsula la partida y el consumo del SSE de cada jugada (o de la apertura de la máquina). */
export function useGameStream() {
  const [state, dispatch] = useReducer(gameReducer, initialState);
  const busy = useRef(false);
  const lastAction = useRef<StreamAction | null>(null);
  const abort = useRef<AbortController | null>(null);

  useEffect(() => () => abort.current?.abort(), []);

  const run = useCallback(async (gameId: string, action: StreamAction) => {
    if (busy.current) return;
    busy.current = true;
    lastAction.current = action;
    const controller = new AbortController();
    abort.current = controller;
    dispatch({ type: "MOVE_STARTED" });
    try {
      const stream =
        action.kind === "move"
          ? streamMove(gameId, action.cell, controller.signal)
          : streamStart(gameId, controller.signal);
      for await (const event of stream) {
        dispatch({ type: "EVENT", event });
      }
    } catch (e) {
      if (!(e instanceof DOMException && e.name === "AbortError")) {
        dispatch({ type: "FAILED", message: messageOf(e) });
      }
    } finally {
      // El backend es la fuente de verdad: resincroniza (p. ej. si se deshizo la jugada).
      if (!controller.signal.aborted) {
        try {
          dispatch({ type: "GAME_LOADED", game: await getGame(gameId) });
        } catch {
          /* se mantiene el estado local */
        }
        busy.current = false;
        dispatch({ type: "MOVE_FINISHED" });
      }
    }
  }, []);

  const startGame = useCallback(
    async (numAgents: number, startingPlayer: StartingPlayer = "human") => {
      abort.current?.abort();
      busy.current = false;
      dispatch({ type: "LOADING" });
      try {
        const game = await createGame(numAgents, startingPlayer);
        dispatch({ type: "GAME_LOADED", game, reset: true });
        // Si empieza la máquina, se pide su apertura enseguida.
        if (game.starting_player === "machine") await run(game.game_id, { kind: "start" });
      } catch (e) {
        dispatch({ type: "FAILED", message: messageOf(e) });
      }
    },
    [run],
  );

  const play = useCallback(
    (cell: number) => {
      if (!state.gameId || state.status !== "in_progress" || state.turn === "machine") return;
      void run(state.gameId, { kind: "move", cell });
    },
    [run, state.gameId, state.status, state.turn],
  );

  const retry = useCallback(() => {
    if (state.gameId && lastAction.current) void run(state.gameId, lastAction.current);
  }, [run, state.gameId]);

  return { state, startGame, play, retry };
}
