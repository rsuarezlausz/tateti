import { createSSEParser } from "./sse";

const block = (name: string, data: object) => `event: ${name}\ndata: ${JSON.stringify(data)}\n\n`;

describe("createSSEParser", () => {
  it("parsea eventos completos", () => {
    const p = createSSEParser();
    expect(p.feed(block("a", { x: 1 }) + block("b", { y: 2 }))).toEqual([
      { name: "a", data: { x: 1 } },
      { name: "b", data: { y: 2 } },
    ]);
  });

  it("junta eventos partidos entre chunks", () => {
    const p = createSSEParser();
    const text = block("agent_message", { message: "hola ñandú" });
    expect(p.feed(text.slice(0, 10))).toEqual([]);
    expect(p.feed(text.slice(10, 30))).toEqual([]);
    expect(p.feed(text.slice(30))).toEqual([
      { name: "agent_message", data: { message: "hola ñandú" } },
    ]);
  });

  it("tolera CRLF, comentarios y bloques inválidos", () => {
    const p = createSSEParser();
    const out = p.feed(": ping\r\n\r\nevent: x\r\ndata: {roto\r\n\r\nevent: ok\r\ndata: {}\r\n\r\n");
    expect(out).toEqual([{ name: "ok", data: {} }]);
  });
});
