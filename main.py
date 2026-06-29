"""Application entry point for the staged vFlow package refactor."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from .backends import configure_matplotlib_backend


LEGACY_SCRIPT = Path(__file__).resolve().parent.parent / "vflow 1.4.5.py"


def _load_legacy_module():
    spec = importlib.util.spec_from_file_location("vflow.legacy_app", LEGACY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load legacy vFlow script: {LEGACY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> None:
    """Launch the existing Tk application through the package entry point."""
    configure_matplotlib_backend(headless=False)
    legacy = _load_legacy_module()

    import matplotlib.pyplot as _plt
    import tkinter as tk

    root = tk.Tk()
    legacy.FlowTabManager(root)

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

