# TicTacToe Agent Factory

POC de Tic-Tac-Toe parametrizable (6×6, 4 en línea por defecto) donde un humano (X) juega contra «la máquina» (O). La jugada de la máquina **no la calcula un algoritmo**: la negocia en vivo un equipo de 1 a 4 agentes LLM con personalidades distintas, creados en tiempo de ejecución por una **Agent Factory** a partir de un `AgentSpec`.

## Requisitos
- Docker y Docker Compose (camino rápido), **o**
- Python 3.12 (3.14 también funciona localmente) y Node 22+.
- Para jugar con modelos reales: una API key de [OpenRouter](https://openrouter.ai). Sin key se usa `LLM_MOCK=true`.

## Configuración
```bash
cp .env.example .env      # en PowerShell: Copy-Item .env.example .env
```
| Variable | Por defecto | Descripción |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Solo la usa el backend. Nunca va al frontend, a logs ni a las imágenes Docker. |
| `OPENROUTER_MODEL` | — | Un único modelo para todos los agentes (elige uno barato). |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | |
| `BOARD_SIZE` | `6` | Tamaño del tablero (2–26). |
| `WIN_LENGTH` | `4` | Fichas en línea para ganar (2–`BOARD_SIZE`). |
| `MAX_ROUNDS` | `3` | Rondas máximas de negociación por jugada. |
| `TACTICAL_HINTS` | `true` | Incluye ayudas tácticas en el prompt (solo informan; nunca eligen la jugada). |
| `TACTICAL_LOOKAHEAD_PLIES` | `4` | Horizonte del análisis táctico en medias jugadas (plies): `0` lo desactiva, máx. `6`. Con 4 se evalúa máquina→humano→máquina→humano y se detectan dobles amenazas futuras (p. ej. dos X consecutivas con extremos libres). Solo informa a los agentes; requiere `TACTICAL_HINTS=true`. |
| `LLM_MOCK` | `false` en el backend / `true` en `.env.example` | Cliente determinista sin credenciales. |
| `CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos (separados por coma). |
| `VITE_API_URL` | `http://localhost:8000` | URL del backend vista desde el navegador; se fija al **construir** el frontend. |

### Usar `LLM_MOCK`
Con `LLM_MOCK=true` no hace falta API key: en la ronda 1 los agentes proponen celdas distintas y desde la ronda 2 convergen, simulando tokens, latencia y costo. Sirve para desarrollar el frontend y correr pruebas sin gastar créditos. Para usar OpenRouter: `LLM_MOCK=false` y completar `OPENROUTER_API_KEY` y `OPENROUTER_MODEL`.

### Cambiar `BOARD_SIZE` / `WIN_LENGTH`
Edita el `.env` y reinicia el backend: las líneas ganadoras se generan dinámicamente y el frontend dibuja el tablero con el `board_size` recibido. Ejemplo: `BOARD_SIZE=3` y `WIN_LENGTH=3` para el 3×3 clásico.

## Ejecutar con Docker
```bash
docker compose up --build
```
- Frontend: <http://localhost:5173> · Backend: <http://localhost:8000> (`/api/health`, `/docs`).
- Si cambias `VITE_API_URL`, reconstruye con `--build`.

## Ejecutar sin Docker
Backend (`pip` + `requirements.txt`):
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
# las variables del .env deben estar en el entorno, p. ej.: $env:LLM_MOCK="true"
.\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```
Frontend:
```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173
```

## Tests
```powershell
cd backend;  .\.venv\Scripts\python -m pytest -q        # un test: pytest tests/test_rules.py::nombre
cd frontend; npm test                                   # un archivo: npx vitest run src/components/Board.test.tsx
```

## Cómo se juega
1. Elige de 1 a 4 agentes, quién empieza (**Humano** o **Máquina**) y pulsa **Nueva partida**. Si empieza la máquina, el frontend pide su apertura enseguida (POST /api/games/{id}/start, SSE con la misma negociación) y luego te toca.
2. Haz tu jugada. Mientras la máquina negocia, el tablero se bloquea y la pestaña **Chat** muestra el debate (rondas, propuestas por coordenada, confianza, decisión final). Al pasar el mouse sobre una burbuja se resalta la celda que propone.
3. La pestaña **Métricas** muestra, por agente y en total, llamadas, tokens, latencia y costo, actualizados en vivo.

Negociación: los agentes hablan en secuencia por rondas; hay consenso si todos proponen la misma celda en una ronda. Sin consenso tras `MAX_ROUNDS`, se sortea **solo entre las propuestas finales más votadas**. Las respuestas inválidas o ilegales se reintentan una vez; si nadie aporta un voto válido, se elige una celda libre al azar y se avisa.

## Arquitectura
```
 Navegador (React + Vite)                     Backend (FastAPI)
┌──────────────────────────┐   REST + SSE   ┌───────────────────────────────────────────┐
│ Board · Chat · Métricas  │ ─────────────► │ api/ (games, agents)  ──► sessions (RAM)  │
│ useGameStream (fetch +   │ ◄───────────── │        │                                  │
│ ReadableStream) + reducer│  eventos tipados│        ▼                                  │
└──────────────────────────┘                │ negotiation/Negotiator ◄─ metrics/        │
                                            │        │  habla por rondas                │
                                            │        ▼                                  │
                                            │ factory/AgentFactory ─► agents/Agent      │
                                            │   (catálogo de AgentSpec)     │           │
                                            │                               ▼           │
                                            │ llm/LLMClient ── OpenRouter │ Mock        │
                                            │ game/ (lógica pura: reglas, render, hints)│
                                            └───────────────────────────────────────────┘
```
- `game/`: única fuente de verdad (reglas, líneas ganadoras dinámicas, render para LLM, ayudas tácticas). El backend valida toda jugada propuesta.
- `POST /api/games` acepta `{"num_agents": 1..4, "starting_player": "human"|"machine"}` (por defecto `human`). Las fichas no cambian (humano = X, máquina = O); solo cambia quién abre. `POST /api/games/{id}/start` hace la apertura de la máquina una sola vez (409 si ya la hizo o si empieza el humano).
- `POST /api/games/{id}/move` responde `text/event-stream` con: `human_move`, `negotiation_started`, `round_started`, `agent_message`, `agent_error`, `consensus` | `tiebreak` | `fallback`, `machine_move`, `metrics_update`, `game_over` (y `error` ante fallos inesperados, deshaciendo la jugada humana).
- Estado de partidas en memoria: se pierde al reiniciar el backend.

## Fuera de alcance
Base de datos, autenticación, multiusuario, modelos distintos por agente y cualquier IA de juego tipo minimax para decidir la jugada de la máquina.

## Funcionamiento interno

### 1. Creación de agentes (Agent Factory)

Cuando el usuario pulsa *Nueva partida*, el backend invoca `AgentFactory.create_team(n)`.

El catálogo (`app/factory/catalog.py`) contiene cuatro **personalidades fijas**, definidas como datos (no clases):

| Orden | Personalidad | Temperatura | Color |
|---|---|---|---|
| 1 | **Estratega** — piensa en patrones, control del centro, dobles amenazas | 0.4 | Azul |
| 2 | **Defensivo** — bloquea al humano, cauto, vigila amenazas abiertas | 0.5 | Verde |
| 3 | **Agresivo** — busca ganar rápido, asume riesgos, empuja al ataque | 0.7 | Rojo |
| 4 | **Caótico** — impredecible, creativo, jugadas no convencionales | 1.0 | Púrpura |

Cada agente es una instancia de `Agent` (`app/agents/agent.py`) que recibe dos cosas en el constructor:

- **`AgentSpec`**: un objeto Pydantic con `id`, `name`, `personality`, `skills`, `system_prompt`, `temperature`, `color` y `avatar`. No contiene el modelo LLM: todos los agentes comparten un único modelo global (configurable por `OPENROUTER_MODEL`).
- **`LLMClient`**: el cliente HTTP que habla con OpenRouter (o el mock). Se inyecta en la fábrica y se comparte entre todos los agentes del equipo.

La personalidad **nunca se codifica con `if` por nombre de agente**: el comportamiento de `Agent.speak()` es genérico. Todo lo que distingue a un agente de otro está en su `AgentSpec`.

```
          AgentFactory
               │
       ┌───────┴────────┐
       ▼                ▼
   Agent(spec, LLM)   Agent(spec, LLM)   ...
     │                      │
     └─── LLMClient ────────┘  (compartido)
```

### 2. Conexión al LLM

La capa `app/llm/` ofrece dos implementaciones intercambiables:

- **`OpenRouterClient`** (`openrouter.py`): envía peticiones HTTP POST a `https://openrouter.ai/api/v1/chat/completions` con el modelo, los mensajes (system + user), `temperature`, `response_format: {type: "json_object"}` para recibir JSON estructurado, y `usage: {include: true}` para obtener tokens y costo. Si el modelo no soporta `response_format`, reintenta sin él. Envía `reasoning: {enabled: false}` para evitar que modelos como `deepseek-v4-flash` gasten tokens «pensando» (el debate mismo es el razonamiento).
- **`MockLLMClient`** (`mock.py`): determinista. Lee las celdas libres del prompt con una regex y, en ronda 1, cada agente elige una celda distinta según un hash de su system prompt. A partir de la ronda 2, todos convergen en la celda más central. Simula tokens, latencia y costo para que métricas y frontend funcionen sin API key.

`build_llm_client(settings)` (`provider.py`) selecciona uno u otro según la variable `LLM_MOCK`.

### 3. Render del tablero para los agentes

Antes de hablar, cada agente recibe el tablero renderizado como texto (`app/game/render.py`):

```
   A B C D E F
 1 . . . . . .
 2 . . . . . .
 3 . . X . . .
 4 . . . . . .
 5 . . . . . .
 6 . . . . . .

Celdas libres (coordenada=índice): A1=0, B1=1, ..., F6=35
```

Si `TACTICAL_HINTS=true` (por defecto), además recibe ayudas tácticas (`app/game/hints.py`) que calculan, en el turno actual:
- Celdas que le dan la victoria inmediata a la máquina.
- Celdas que bloquean una victoria inmediata del humano.
- Amenazas abiertas de `WIN_LENGTH - 1` fichas consecutivas con ambos extremos libres (posibles dobles amenazas).

Estas ayudas **solo informan** a los agentes. El backend nunca elige la jugada por su cuenta.

### 4. Negociación por rondas

Cuando el humano hace una jugada (`POST /api/games/{id}/move`), el backend abre una negociación.

El `Negotiator` (`app/negotiation/engine.py`) recibe:
- La lista de agentes (en orden del catálogo: Estratega, Defensivo, Agresivo, Caótico).
- El tablero, el tamaño y la longitud de racha ganadora.
- `max_rounds` (por defecto 3, configurable por `MAX_ROUNDS`).
- Un `MetricsCollector` compartido para registrar todas las llamadas.
- Un generador de números aleatorios (inyectable para tests).

**Protocolo paso a paso:**

```
Humano juega C3 ──► POST /api/games/{id}/move

                    ┌─ NegotiationStarted(max_rounds, agentes)
                    │
                    ├─ RoundStarted(1)
                    │   ├─ Estratega habla  ──► agent_message
                    │   ├─ Defensivo habla   ──► agent_message
                    │   ├─ Agresivo habla   ──► agent_message
                    │   ├─ Caótico habla    ──► agent_message
                    │   └─ ¿Todos proponen lo mismo? → NO
                    │
                    ├─ RoundStarted(2)
                    │   ├─ Estratega habla  ──► agent_message
                    │   ├─ Defensivo habla   ──► agent_message
                    │   ├─ Agresivo habla   ──► agent_message
                    │   ├─ Caótico habla    ──► agent_message
                    │   └─ ¿Todos proponen lo mismo? → SÍ
                    │
                    └─ Consensus(move, round=2)
                       │
                       ▼
                    La máquina juega (tablero actualizado)
                    ──► machine_move → metrics_update → game_over (si aplica)
```

**En cada turno de un agente:**

1. El `Negotiator` construye un `NegotiationContext` con:
   - El tablero renderizado y las celdas libres.
   - Las ayudas tácticas (si están activas).
   - El número de ronda actual y el máximo.
   - El **transcript completo de la negociación en curso**: lo que cada agente dijo en rondas anteriores, con su nombre, la ronda en que lo dijo, la celda que propuso y su mensaje de texto.

2. Se llama a `Agent.speak(context, correction=None)`:
   - Arma el prompt (`system` + `user`).
   - El **system prompt** combina la personalidad del agente (de su `AgentSpec`) con reglas comunes del juego (ganar con N fichas, responder solo JSON, máximo 280 caracteres, español y celdas por coordenada).
   - El **user prompt** incluye el tablero, las celdas libres, las ayudas tácticas y el debate previo.

   **Ejemplo del user prompt que ve el Caótico en ronda 2:**
   ```
   Ronda 2 de 3.

   Tablero (X = humano, O = máquina, . = vacía):
      A B C D E F
   1  . . . . . .
   2  . . . . . .
   3  . . X . . .
   4  . . . . . .
   5  . . . . . .
   6  . . . . . .

   Celdas libres (coordenada=índice): A1=0, B1=1 ..., F6=35

   Ayudas tácticas (informativas; la decisión es de ustedes):
   - Victoria inmediata para la máquina (O): ninguna
   - Jugadas para bloquear una victoria inmediata del humano (X): D3, C4, B3
   - Amenazas abiertas de 3 en línea: ninguna

   Debate hasta ahora:
   - Estratega (ronda 1) propone D3: "Para controlar el centro y bloquear su posible línea..."
   - Defensivo (ronda 1) propone D3: "Apoyo la jugada en D3 para bloquear..."
   - Agresivo (ronda 1) propone D3: "Coloco en D3 para iniciar una doble amenaza..."

   Considera las propuestas y argumentos anteriores: puedes ceder ante un buen argumento
   o insistir en el tuyo y explicar por qué.

   Responde con el JSON indicado.
   ```

3. El agente responde con un JSON (forzado por `response_format`):
   ```json
   {
     "message": "Propongo D3: es la mejor opción táctica ahora.",
     "proposed_move": 15,
     "confidence": 0.85
   }
   ```

4. El `Negotiator` valida:
   - ¿El JSON es sintácticamente válido? Si no, **reintenta 1 vez** con un mensaje de corrección que lista las celdas libres.
   - ¿`proposed_move` es una celda libre? Si no, **reintenta 1 vez**.
   - Si tras el reintento sigue fallando, emite `AgentErrorEvent` y esa intervención **no cuenta como voto** en esta ronda.

5. **Cada llamada al LLM se registra** en el `MetricsCollector`: agente, ronda, tokens (prompt/completion/total), latencia y costo. También las llamadas fallidas, para que las métricas reflejen el gasto real.

### 5. Cómo se enteran los agentes del razonamiento de los demás

El **transcript** es el mecanismo clave. Es una lista de `TranscriptEntry` que incluye: `agent_id`, `agent_name`, `round_number`, el texto del mensaje y la celda propuesta. Este transcript se incluye en el user prompt de **cada agente en la ronda actual**, con formato legible:

```
Debate hasta ahora:
- Estratega (ronda 1) propone D3: "Para controlar el centro..."
- Defensivo (ronda 1) propone D3: "Apoyo a Estratega..."
- Agresivo (ronda 1) propone D3: "Atacamos ya..."
```

A partir de la ronda 2, el prompt además añade:

> Considera las propuestas y argumentos anteriores: puedes ceder ante un buen argumento o insistir en el tuyo y explicar por qué.

Esto permite que los agentes realmente debatan: pueden reconocer que otro agente tiene razón, ceder, o defender su posición con nuevos argumentos. Como cada agente tiene su propia personalidad y temperatura, los desacuerdos surgen naturalmente.

**Control del contexto**: el transcript solo contiene los mensajes de la **negociación en curso** (no de turnos anteriores de la máquina). Tras cada jugada de la máquina el transcript se reinicia.

### 5 bis. Estrategia, análisis táctico y evaluación de propuestas

Además del tablero y las ayudas básicas, cada negociación calcula **una sola vez** un análisis táctico a `TACTICAL_LOOKAHEAD_PLIES` medias jugadas (`app/game/lookahead.py`). Busca secuencias de amenazas (el atacante juega solo jugadas que crean victorias inmediatas; el defensor está obligado a bloquear), lo que detecta dobles amenazas futuras: por ejemplo, dos X consecutivas con extremos libres se convierten en tres abiertas y no se pueden bloquear ambos extremos. El informe indica la amenaza, qué jugadas de la máquina la previenen y las oportunidades de victoria forzada de la máquina.

Cada agente recibe además:
- **Prioridades comunes** en su system prompt: 1) ganar si puede, 2) bloquear una victoria inmediata, 3) prevenir las amenazas futuras del análisis (no proponer jugadas marcadas `INSEGURA`), 4) solo entonces aplicar su estrategia.
- **Valor posicional** de las celdas (potencial ofensivo y defensivo) para que cada perfil elija según su estilo: Estratega (centro y estructuras), Defensivo (cortar líneas del humano), Agresivo (ampliar líneas propias y amenazar), Caótico (la jugada segura menos obvia). Los perfiles son datos del catálogo, nunca lógica por nombre.
- Tras cada propuesta, una **evaluación del sistema** (`segura` / `INSEGURA: deja al humano una victoria forzada en N jugadas`) que ven los agentes que hablan después, para que puedan objetarla o apoyarla.

Todo esto **solo orienta**: el backend no rechaza jugadas por estrategia; únicamente valida que la celda esté libre. La decisión final sigue saliendo de la negociación.
### 6. Decisiones finales

Al terminar la última ronda sin consenso:

1. Se cuentan las **propuestas finales** de cada agente (la última propuesta válida de cada uno, independientemente de la ronda en que la hicieron).
2. Si todos votan lo mismo → **Consenso**.
3. Si hay varias propuestas, se agrupan por celda y se elige **al azar entre las jugadas más votadas** (las que tienen la frecuencia máxima).
4. Si ningún agente aportó un voto válido (todos fallaron) → se elige una celda libre **al azar** y se emite `Fallback` con el motivo.

Todo el proceso (rondas, intervenciones, decisión final) se transmite al frontend como eventos SSE para que el chat se actualice en vivo.

### 7. Flujo completo (humano juega una celda)

```
Humano hace clic en C3
        │
        ▼
Frontend: POST /api/games/{id}/move  { "cell": 14 }
        │
        ▼
Backend valida: ¿celda válida y libre? ¿turno del humano? ¿partida activa?
  Si no → HTTP 409/422
  Si sí →
        │
        ├── Aplica la jugada humana (C3 = X)
        │
        ├── ¿El humano ganó con esa jugada?
        │     Sí → SSE: human_move → game_over (humano ganó)
        │     No  →
        │
        ├── Negotiator.run(board, 6, 4) → genera eventos SSE:
        │     negotiation_started
        │     round_started (1)
        │       agent_message (Estratega)
        │       metrics_update
        │       agent_message (Defensivo)
        │       metrics_update
        │       ...
        │     (si no hay consenso) round_started (2) ...
        │     consensus / tiebreak / fallback
        │
        ├── Aplica la jugada de la máquina (celda elegida = O)
        │
        ├── SSE: machine_move, metrics_update
        │
        └── ¿La máquina ganó o es empate?
              Sí → SSE: game_over (máquina ganó / empate)
              No  → SSE sin game_over (sigue el juego)
        │
        ▼
Frontend: el hook useGameStream recibe cada evento y actualiza el estado
          (tablero, chat, métricas) a través del reducer.
          Al terminar el stream, resincroniza con GET /api/games/{id}.
```

### 8. Manejo de errores y robustez

- **JSON inválido o jugada ilegal**: reintento 1 vez con corrección explícita.
- **Error del proveedor LLM** (timeout, HTTP 5xx): se marca como fallo; se reintenta.
- **Cliente se desconecta durante el stream**: el backend detecta la desconexión y **deshace la jugada humana** en un bloque `finally`, dejando la partida en el mismo estado anterior para poder reintentar.
- **Fallo inesperado** (excepción no controlada): también deshace la jugada humana y emite un evento `error` genérico (sin filtrar credenciales ni detalles internos).
- **Partida inexistente por reinicio del backend**: el frontend muestra "La partida ya no existe (el servidor se reinició). Pulsa «Nueva partida»."
