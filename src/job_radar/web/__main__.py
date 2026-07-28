"""Run the web app: ``python -m job_radar.web`` (dev) or via uvicorn (prod)."""

from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "job_radar.web.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("WEB_RELOAD")),
    )


if __name__ == "__main__":
    main()
