from app.agents.models import NegotiationContext
from app.agents.spec import AgentSpec
from app.game.coords import index_to_coord
from app.game.hints import render_hints
from app.game.render import render_for_llm

COMMON_RULES = (
    "Eres parte de un equipo que negocia la jugada de la máquina (O) en un Tic-Tac-Toe contra un "
    "humano (X). Ganar requiere {win} fichas consecutivas propias en horizontal, vertical o diagonal. "
    "Debes proponer una celda libre. Habla siempre en español, con el tono de tu personalidad, "
    "y cita las celdas por coordenada (por ejemplo C3).\n"
    "Prioridades comunes, en este orden (tu personalidad decide solo a partir del punto 4):\n"
    "1) Si puedes ganar ya, hazlo.\n"
    "2) Si el humano tiene una victoria inmediata, bloquéala.\n"
    "3) Si el análisis táctico indica amenazas futuras del humano, propón una jugada que las "
    "prevenga; no propongas una jugada marcada como INSEGURA salvo que no exista alternativa. "
    "Si una propuesta del debate está marcada como INSEGURA, objétala y propón una segura.\n"
    "4) Entre las jugadas seguras, elige según tu estrategia y justifícala en tu mensaje.\n"
    'Responde SOLO con un objeto JSON: {{"message": "<máx 280 caracteres>", '
    '"proposed_move": <índice numérico de una celda libre>, "confidence": <0 a 1>}}.'
)


def build_system_prompt(spec: AgentSpec, win_length: int) -> str:
    return (
        f"Tu nombre es {spec.name} ({spec.personality}).\n{spec.system_prompt}\n\n"
        + COMMON_RULES.format(win=win_length)
    )


def build_user_prompt(ctx: NegotiationContext) -> str:
    parts = [
        f"Ronda {ctx.round_number} de {ctx.max_rounds}.",
        render_for_llm(ctx.board, ctx.board_size),
    ]
    if ctx.tactical_hints:
        parts.append(render_hints(ctx.board, ctx.board_size, ctx.win_length))
    if ctx.lookahead_report:
        parts.append(ctx.lookahead_report)
    if ctx.transcript:
        lines = [
            f'- {e.agent_name} (ronda {e.round_number}) propone '
            f'{index_to_coord(e.proposed_move, ctx.board_size)}: "{e.message}"'
            + (f" [evaluación del sistema: {e.assessment}]" if e.assessment else "")
            for e in ctx.transcript
        ]
        parts.append("Debate hasta ahora:\n" + "\n".join(lines))
    if ctx.round_number >= 2:
        parts.append(
            "Considera las propuestas y argumentos anteriores: puedes ceder ante un buen "
            "argumento o insistir en el tuyo y explicar por qué."
        )
    parts.append("Responde con el JSON indicado.")
    return "\n\n".join(parts)
