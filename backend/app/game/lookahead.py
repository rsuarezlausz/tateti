"""Análisis táctico con horizonte acotado (en plies = medias jugadas).

Busca secuencias de amenazas (threat-space): el atacante solo juega movimientos que crean
victorias inmediatas y el defensor está obligado a bloquear. Eso cubre dobles amenazas
(p. ej. dos X consecutivas con extremos libres -> tres abiertas -> no se pueden bloquear
ambos extremos) sin explotar combinatoriamente. Es solo una ayuda informativa: la jugada
de la máquina sigue saliendo de la negociación de los agentes.
"""

from dataclasses import dataclass

from app.game.coords import index_to_coord
from app.game.hints import winning_moves
from app.game.rules import HUMAN, MACHINE, Board, apply_move, check_result, legal_moves, opponent

MAX_LOOKAHEAD_PLIES = 6


@dataclass(frozen=True)
class ForcedWin:
    first_move: int  # primera jugada del atacante de la secuencia
    plies: int  # medias jugadas hasta ganar, contando las del atacante y las del defensor


@dataclass(frozen=True)
class TacticalReport:
    horizon: int
    machine_win: ForcedWin | None  # la máquina gana a la fuerza dentro del horizonte
    human_threats: tuple[ForcedWin, ...]  # secuencias con las que X gana si no se previene
    safe_moves: tuple[int, ...] | None  # jugadas de O que evitan todas; None si no hay amenaza

    @property
    def lost(self) -> bool:
        """Hay amenaza y ninguna jugada la evita dentro del horizonte."""
        return bool(self.human_threats) and self.safe_moves == ()


def _wins(board: Board, size: int, win: int, attacker: str, plies: int, memo: dict) -> list[ForcedWin]:
    """Todas las primeras jugadas con las que `attacker` (que mueve ahora) gana a la fuerza
    en <= `plies` medias jugadas, encadenando solo amenazas."""
    key = (board, attacker, plies)
    if key in memo:
        return memo[key]
    result: list[ForcedWin] = []
    defender = opponent(attacker)
    immediate = winning_moves(board, size, win, attacker)
    if plies >= 1 and immediate:
        result = [ForcedWin(m, 1) for m in immediate]
    elif plies >= 3:
        defender_wins = winning_moves(board, size, win, defender)
        if len(defender_wins) < 2:  # con dos amenazas rivales no se puede frenar ambas
            candidates = defender_wins or legal_moves(board)
            for h in candidates:
                forced = _forcing_line(board, size, win, attacker, h, plies, memo)
                if forced is not None:
                    result.append(forced)
    memo[key] = result
    return result


def _forcing_line(
    board: Board, size: int, win: int, attacker: str, h: int, plies: int, memo: dict
) -> ForcedWin | None:
    defender = opponent(attacker)
    b1 = apply_move(board, h, attacker)
    threats = winning_moves(b1, size, win, attacker)
    if not threats or winning_moves(b1, size, win, defender):
        return None  # no amenaza, o el defensor gana antes
    if len(threats) >= 2:
        return ForcedWin(h, 3)  # doble amenaza: h, bloqueo (insuficiente), victoria
    b2 = apply_move(b1, threats[0], defender)  # bloqueo forzado
    if check_result(b2, size, win).winner == defender:
        return None
    if plies - 2 < 1:
        return None
    sub = _wins(b2, size, win, attacker, plies - 2, memo)
    return ForcedWin(h, 2 + sub[0].plies) if sub else None


def analyze(board: Board, board_size: int, win_length: int, plies: int) -> TacticalReport:
    """Análisis con la máquina (O) a punto de mover. `plies` = horizonte en medias jugadas."""
    memo: dict = {}
    machine = _wins(board, board_size, win_length, MACHINE, plies, memo)
    machine_win = min(machine, key=lambda w: w.plies) if machine else None
    # Si O jugara "pasando", ¿con qué secuencias ganaría X en los plies restantes?
    threats = _wins(board, board_size, win_length, HUMAN, plies - 1, memo)
    if not threats:
        return TacticalReport(plies, machine_win, (), None)
    safe = []
    for move in legal_moves(board):
        after = apply_move(board, move, MACHINE)
        if check_result(after, board_size, win_length).winner == MACHINE:
            safe.append(move)
        elif not _wins(after, board_size, win_length, HUMAN, plies - 1, memo):
            safe.append(move)
    ordered = tuple(sorted(threats, key=lambda w: (w.plies, w.first_move)))
    return TacticalReport(plies, machine_win, ordered, tuple(safe))


def _coords(cells, size: int, limit: int = 12) -> str:
    shown = [index_to_coord(c, size) for c in list(cells)[:limit]]
    extra = len(list(cells)) - limit
    return ", ".join(shown) + (f" y {extra} más" if extra > 0 else "")


def render_lookahead(report: TacticalReport, board_size: int) -> str:
    """Texto para el prompt: amenazas futuras detectadas y jugadas que las previenen."""
    n = report.horizon
    lines = [f"Análisis táctico a {n} jugadas (medias jugadas, informativo):"]
    if report.machine_win:
        w = report.machine_win
        lines.append(
            f"- Oportunidad: la máquina (O) puede ganar a la fuerza jugando "
            f"{index_to_coord(w.first_move, board_size)} (en {w.plies} jugadas)."
        )
    if not report.human_threats:
        lines.append("- Sin amenazas forzadas del humano (X) dentro del horizonte.")
        return "\n".join(lines)
    firsts = [t.first_move for t in report.human_threats]
    soonest = report.human_threats[0].plies
    lines.append(
        f"- AMENAZA: si no se previene, el humano (X) puede ganar a la fuerza en {soonest} "
        f"jugadas empezando por: {_coords(dict.fromkeys(firsts), board_size, 8)}."
    )
    if report.safe_moves:
        lines.append(
            "- Jugadas de la máquina que previenen esas amenazas dentro del horizonte: "
            f"{_coords(report.safe_moves, board_size)}."
        )
    else:
        lines.append(
            "- Ninguna jugada evita la derrota dentro del horizonte; elijan la que más la demore."
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class MoveAssessment:
    """Consecuencias tácticas de una jugada concreta de la máquina (para el debate)."""

    wins: bool  # la jugada gana la partida
    human_win: ForcedWin | None  # victoria forzada que le deja al humano dentro del horizonte
    own_threats: tuple[int, ...]  # celdas con victoria inmediata para O tras la jugada


def assess_move(board: Board, board_size: int, win_length: int, plies: int, move: int) -> MoveAssessment:
    """Evalúa `move` (de O) con el mismo horizonte: ¿gana?, ¿deja una victoria forzada a X?"""
    after = apply_move(board, move, MACHINE)
    if check_result(after, board_size, win_length).winner == MACHINE:
        return MoveAssessment(True, None, ())
    human = _wins(after, board_size, win_length, HUMAN, plies - 1, {})
    human_win = min(human, key=lambda w: (w.plies, w.first_move)) if human else None
    return MoveAssessment(
        False, human_win, tuple(winning_moves(after, board_size, win_length, MACHINE))
    )


def render_assessment(a: MoveAssessment, board_size: int) -> str:
    if a.wins:
        return "esta jugada gana la partida"
    if a.human_win:
        parts = [
            f"INSEGURA: deja al humano una victoria forzada en {a.human_win.plies} jugadas "
            f"(empezando por {index_to_coord(a.human_win.first_move, board_size)})"
        ]
    else:
        parts = ["segura: no deja victorias forzadas al humano dentro del horizonte"]
    if len(a.own_threats) >= 2:
        parts.append(f"crea doble amenaza propia ({_coords(a.own_threats, board_size)})")
    elif a.own_threats:
        parts.append(f"crea una amenaza propia en {_coords(a.own_threats, board_size)}")
    return "; ".join(parts)
