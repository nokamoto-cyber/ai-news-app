"""
server.py — ローカル開発サーバー

「最新ニュースを取得」ボタンから更新処理をトリガーするためのサーバー。

起動方法:
  python scripts/server.py

アクセス:
  http://localhost:8080

機能:
  - public/ ディレクトリを静的サーバーとして配信
  - GET /api/update → main.py を実行して articles.json を更新
"""

import http.server
import json
import os
import subprocess
import sys
import threading
import webbrowser
from urllib.parse import urlparse

# ============================================================
# 定数
# ============================================================

PORT = 8080
PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "public")
SCRIPTS_DIR = os.path.dirname(__file__)

# 更新処理の多重実行を防ぐフラグ
_updating = False
_update_lock = threading.Lock()


# ============================================================
# HTTPハンドラ
# ============================================================

class Handler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/api/update":
            self._handle_update()
        else:
            super().do_GET()

    def _handle_update(self):
        """main.py を実行して articles.json を更新する"""
        global _updating

        with _update_lock:
            if _updating:
                self._json_response({"status": "busy", "message": "更新処理が実行中です"}, 429)
                return
            _updating = True

        try:
            python = sys.executable
            main_py = os.path.join(SCRIPTS_DIR, "main.py")

            result = subprocess.run(
                [python, main_py],
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode == 0:
                self._json_response({"status": "ok", "message": "更新完了"})
                print("\n[server] ✅ 記事更新完了")
            else:
                error_msg = result.stderr[-500:] if result.stderr else "不明なエラー"
                self._json_response(
                    {"status": "error", "message": error_msg}, 500
                )
                print(f"\n[server] ❌ 更新失敗:\n{error_msg}")
        except subprocess.TimeoutExpired:
            self._json_response({"status": "error", "message": "タイムアウト（120秒）"}, 500)
        finally:
            with _update_lock:
                _updating = False

    def _json_response(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        # /api/update 以外のアクセスログは省略してターミナルをすっきりさせる
        if args and isinstance(args[0], str) and ("/api/" in args[0] or args[0].startswith("GET / ")):
            print(f"[server] {self.address_string()} → {args[0].split()[1]}")


# ============================================================
# 起動
# ============================================================

def start():
    os.chdir(PUBLIC_DIR)

    httpd = http.server.HTTPServer(("localhost", PORT), Handler)

    url = f"http://localhost:{PORT}"
    print("=" * 50)
    print("🌐 AI ニュースアプリ — ローカルサーバー起動")
    print(f"   URL: {url}")
    print("=" * 50)
    print("   ブラウザで上記URLを開いてください")
    print("   終了するには Ctrl+C を押してください")
    print()

    # 少し待ってからブラウザを自動起動
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nサーバーを停止しました。")


if __name__ == "__main__":
    start()
