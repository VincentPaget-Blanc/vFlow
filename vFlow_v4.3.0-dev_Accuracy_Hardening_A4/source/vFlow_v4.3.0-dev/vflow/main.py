"""Application entry point for vFlow."""

from __future__ import annotations

import importlib
import sys

from .backends import configure_matplotlib_backend


LEGACY_MODULE_NAME = "vflow.legacy.vflow_app"


def _load_legacy_module():
    """Return the packaged legacy compatibility module lazily.

    The v4.2 release has a single packaged source authority; there is no
    duplicate standalone launcher file to synchronize.
    """
    return importlib.import_module(LEGACY_MODULE_NAME)


def main() -> None:
    """Launch the Tk application through the installed/package entry point."""
    configure_matplotlib_backend(headless=False)
    from vflow.ui.tab_manager import FlowTabManager

    import matplotlib.pyplot as _plt
    import tkinter as tk

    root = tk.Tk()
    FlowTabManager(root)

    def _on_close():
        try:
            _plt.close("all")
        except Exception:
            pass
        root.quit()
        root.destroy()
        sys.exit(0)

    root.protocol("WM_DELETE_WINDOW", _on_close)
    root.mainloop()
    sys.exit(0)


if __name__ == "__main__":
    main()
