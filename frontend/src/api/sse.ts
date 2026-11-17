import type { SSEEvent } from "../types";

/** Parser incremental de Server-Sent Events (el POST impide usar EventSource). */
export function createSSEParser() {
  let buffer = "";
  return {
    feed(chunk: string): SSEEvent[] {
      buffer += chunk.replace(/\r\n/g, "\n");
      const events: SSEEvent[] = [];
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const event = parseBlock(block);
        if (event) events.push(event);
      }
      return events;
    },
  };
}

function parseBlock(block: string): SSEEvent | null {
  let name = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue;
    if (line.startsWith("event:")) name = line.slice(6).trim();
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
  }
  if (data.length === 0) return null;
  try {
    return { name, data: JSON.parse(data.join("\n")) };
  } catch {
    return null;
  }
}
