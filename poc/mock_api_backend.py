import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os

HOST = "127.0.0.1"
PORT = int(os.environ.get("MOCK_PORT", "5001"))

class MockHandler(BaseHTTPRequestHandler):
    server_version = "MockServer/0.1"

    def _set_common(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")  # simple CORS
        self.end_headers()

    def _serve_file(self, filename):
        try:
            file = Path(__file__).parent / filename
            data = json.loads(file.read_text(encoding="utf-8"))
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._set_common(200)
            self.wfile.write(body)
        except FileNotFoundError:
            self._set_common(500)
            self.wfile.write(b'{"error":"data file not found"}')
        except json.JSONDecodeError:
            self._set_common(500)
            self.wfile.write(b'{"error":"invalid JSON"}')

    def do_GET(self):
        if self.path == "/api/v1/enterprises":
            self._serve_file("response_enterprises.json")
        elif self.path == "/api/v1/fields":
            self._serve_file("response_fields.json")
        else:
            self._set_common(404)
            self.wfile.write(b'{"error":"not found"}')

    def log_message(self, format, *args):
        # Quieter logging; comment out to see default logs
        print(f"[{self.log_date_time_string()}] {self.command} {self.path} {args}")

def run():
    server = ThreadingHTTPServer((HOST, PORT), MockHandler)
    print(f"Mock server running on http://{HOST}:{PORT}")
    print("Endpoints: /api/v1/enterprises, /api/v1/fields")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        server.server_close()

if __name__ == "__main__":
    run()
