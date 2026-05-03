from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .models import StageEvent
from .pipeline import DeepResearchPipeline


INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Deep Research</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f7f7f4; color: #202124; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px; display: grid; gap: 20px; }
    form { display: grid; grid-template-columns: 1fr auto; gap: 8px; }
    input, button { font: inherit; border: 1px solid #b9b9b2; border-radius: 6px; padding: 10px 12px; }
    button { background: #1f6f5b; color: white; border-color: #1f6f5b; cursor: pointer; }
    section { display: grid; gap: 10px; }
    pre, ol, ul { background: white; border: 1px solid #ddddd6; border-radius: 6px; padding: 14px; }
    pre { white-space: pre-wrap; line-height: 1.5; min-height: 160px; }
    li { margin: 6px 0; }
    @media (max-width: 640px) { form { grid-template-columns: 1fr; } main { padding: 20px 12px; } }
  </style>
</head>
<body>
  <main>
    <form id="form">
      <input id="query" value="의료 신경과학 공부하는 방법" aria-label="research query">
      <button type="submit">Run</button>
    </form>
    <section>
      <ol id="events"></ol>
      <pre id="answer"></pre>
      <ul id="sources"></ul>
    </section>
  </main>
  <script>
    const form = document.querySelector("#form");
    const events = document.querySelector("#events");
    const answer = document.querySelector("#answer");
    const sources = document.querySelector("#sources");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      events.textContent = "";
      answer.textContent = "";
      sources.textContent = "";
      const response = await fetch("/research", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({query: document.querySelector("#query").value})
      });
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, {stream: true});
        const frames = buffer.split("\\n\\n");
        buffer = frames.pop();
        for (const frame of frames) {
          const dataLine = frame.split("\\n").find((line) => line.startsWith("data: "));
          if (!dataLine) continue;
          const payload = JSON.parse(dataLine.slice(6));
          if (payload.stage) {
            const item = document.createElement("li");
            item.textContent = `${payload.stage}: ${payload.message}`;
            events.appendChild(item);
          }
          if (payload.answer) {
            answer.textContent = payload.answer;
            for (const source of payload.ranked_sources || []) {
              const item = document.createElement("li");
              item.textContent = `${source.result.source_id} ${source.result.title}`;
              sources.appendChild(item);
            }
          }
        }
      }
    });
  </script>
</body>
</html>
"""


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), ResearchHandler)
    print(f"Serving deep research UI at http://{host}:{port}")
    server.serve_forever()


class ResearchHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        body = INDEX_HTML.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/research":
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            query = str(payload["query"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Expected JSON body with a query field.")
            return

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def on_event(event: StageEvent) -> None:
            self.wfile.write(_sse("stage", asdict(event)))
            self.wfile.flush()

        bundle = DeepResearchPipeline(on_event=on_event).run(query)
        self.wfile.write(_sse("final", asdict(bundle)))
        self.wfile.flush()

    def log_message(self, format: str, *args) -> None:
        return


def _sse(event: str, payload: dict) -> bytes:
    lines = [f"event: {event}", f"data: {json.dumps(payload, ensure_ascii=False)}", ""]
    return ("\n".join(lines) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the deep research SSE server and minimal UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
