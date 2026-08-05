from __future__ import annotations

import os
import threading
import time
import webbrowser

import uvicorn


def _open_browser(host: str, port: int) -> None:
    if os.getenv("LIFEGRAPH_AUTO_OPEN_BROWSER", "1") not in {"1", "true", "TRUE"}:
        return
    time.sleep(1.2)
    webbrowser.open(f"http://{host}:{port}")


def main() -> None:
    host = os.getenv("LIFEGRAPH_HOST", "127.0.0.1")
    port = int(os.getenv("LIFEGRAPH_PORT", "8765"))
    threading.Thread(target=_open_browser, args=(host, port), daemon=True).start()
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
