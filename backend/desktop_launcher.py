"""Masaüstü uygulaması giriş noktası.

FastAPI sunucusunu arka planda başlatır, hazır olunca pywebview ile yerel bir pencere açar.
Geliştirirken de çalıştırılabilir:  python3 desktop_launcher.py
"""
import multiprocessing
import os
import socket
import sys
import threading
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_until_ready(port: int, timeout_s: float = 40.0) -> bool:
    deadline = time.time() + timeout_s
    url = f"http://127.0.0.1:{port}/api/health"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def main():
    import uvicorn

    from main import app

    port = _free_port()
    threading.Thread(target=lambda: uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning"), daemon=True).start()
    if not _wait_until_ready(port):
        print("Uyarı: sunucu beklenen sürede ayağa kalkmadı.")

    if "--smoke-test" in sys.argv:
        import json
        for route in ("/api/health", "/api/status", "/"):
            with urllib.request.urlopen(f"http://127.0.0.1:{port}{route}", timeout=20) as r:
                if r.status != 200:
                    raise SystemExit(f"Paket kontrolü başarısız: {route}")
                if route == "/" and "/assets/" not in r.read().decode():
                    raise SystemExit("Paketlenmiş arayüz bulunamadı.")
        print(json.dumps({"packaged_smoke_test": "passed", "port": port}), flush=True)
        return

    import webview

    webview.create_window("Kalıp Değişim Kaybı", f"http://127.0.0.1:{port}", width=1380, height=900, min_size=(760, 560),
                          background_color="#12141a")
    webview.start()


def _log_path() -> str:
    d = os.path.join(os.path.expanduser("~"), "Library", "Logs") if sys.platform == "darwin" else os.path.expanduser("~")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "KalipDegisimKaybi.log")


if __name__ == "__main__":
    # PyInstaller'da alt süreçlerin uygulamayı yeniden başlatmasını engeller (en başta olmalı)
    multiprocessing.freeze_support()
    try:
        main()
    except BaseException:  # noqa: BLE001  (pencere açılamazsa nedenini günlüğe yaz)
        import traceback
        with open(_log_path(), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n" + traceback.format_exc() + "\n")
        raise
