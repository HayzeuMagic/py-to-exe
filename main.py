"""PyForge entry point."""
from __future__ import annotations

import multiprocessing
import sys
import traceback

from ui.main_window import MainWindow
from utils.logging_config import configure_logging, get_logger


def main() -> int:
    logger = get_logger("main")
    try:
        configure_logging()
        app = MainWindow()
        app.mainloop()
        return 0
    except Exception:  # noqa: BLE001 - last-resort handler at the process boundary
        logger.critical("Unhandled exception, PyForge is exiting:\n%s", traceback.format_exc())
        print("PyForge encountered an unexpected error and had to close. See the log for details.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    # Required when frozen with PyInstaller on Windows: without this, a
    # library using multiprocessing could re-launch this entire script
    # (and therefore the whole GUI) in each worker process.
    multiprocessing.freeze_support()
    sys.exit(main())
