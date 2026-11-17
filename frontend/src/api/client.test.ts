import { ApiError, createGame, streamMove, streamStart } from "./client";

function streamOf(chunks: string[]): Response {
  const enc = new TextEncoder();
  const body = new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(enc.encode(c)));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

async function collect(gen: AsyncGenerator<unknown>) {
  const out: unknown[] = [];
  for await (const e of gen) out.push(e);
  return out;
}

afterEach(() => vi.unstubAllGlobals());

describe("streamMove", () => {
  it("hace POST con fetch y emite eventos del ReadableStream", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        streamOf(['event: human_move\ndata: {"cell":14}\n\nevent: con', 'sensus\ndata: {"move":0}\n\n']),
      );
    vi.stubGlobal("fetch", fetchMock);
    const events = await collect(streamMove("g1", 14));
    expect(events).toEqual([
      { name: "human_move", data: { cell: 14 } },
      { name: "consensus", data: { move: 0 } },
    ]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/games\/g1\/move$/);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ cell: 14 });
  });

  it("convierte errores HTTP en ApiError con el detalle del backend", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Celda ocupada: 14" }), { status: 409 })),
    );
    await expect(collect(streamMove("g1", 14))).rejects.toMatchObject({
      status: 409,
      message: "Celda ocupada: 14",
    });
  });

  it("informa error de red en español", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fail")));
    const err = await collect(streamMove("g1", 1)).catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.message).toContain("No se pudo conectar");
  });
});

describe("starting_player y apertura", () => {
  it("createGame envía starting_player (human por defecto)", async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: RequestInit) => new Response(JSON.stringify({ game_id: "g" }), { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    await createGame(2);
    await createGame(3, "machine");
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ num_agents: 2, starting_player: "human" });
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({ num_agents: 3, starting_player: "machine" });
  });

  it("streamStart hace POST a /start sin cuerpo y emite los eventos", async () => {
    const fetchMock = vi.fn().mockResolvedValue(streamOf(['event: negotiation_started\ndata: {"max_rounds":3}\n\n']));
    vi.stubGlobal("fetch", fetchMock);
    const events = await collect(streamStart("g1"));
    expect(events).toEqual([{ name: "negotiation_started", data: { max_rounds: 3 } }]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toMatch(/\/api\/games\/g1\/start$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeUndefined();
  });

  it("streamStart convierte un 409 en ApiError con el detalle", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "La máquina ya hizo su apertura" }), { status: 409 })),
    );
    await expect(collect(streamStart("g1"))).rejects.toMatchObject({ status: 409 });
  });
});