import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure simple, consistent logging for the app.

    Format: time level logger message k=v ...
    """
    root = logging.getLogger()
    if root.handlers:
        # Respect existing (e.g., uvicorn) but align level
        root.setLevel(level.upper())
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )
    handler.setFormatter(formatter)

    root.addHandler(handler)
    root.setLevel(level.upper())

