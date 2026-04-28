"""ローカル確認用サーバー（no-cache対応）"""
import http.server, os

PUBLIC = os.path.join(os.path.dirname(__file__), "public")

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=PUBLIC, **kw)
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        super().end_headers()
    def log_message(self, *a): pass

if __name__ == "__main__":
    with http.server.HTTPServer(("localhost", 3456), Handler) as s:
        print(f"http://localhost:3456")
        s.serve_forever()
