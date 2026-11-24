"""Development server entry point used by INSTALL.md and the Docker image."""

from __future__ import annotations

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        threaded=True,
        debug=app.config["DEBUG"],
    )
