"""Launch The Pasta Machine: ``python -m pasta.frontends.desktop``."""
import sys

try:
    import PySide6  # noqa: F401
except ImportError:  # pragma: no cover - optional dependency
    print("The desktop app needs PySide6. Install it with: pip install PySide6")
    sys.exit(1)

from pasta.frontends.desktop.app import main

if __name__ == "__main__":  # pragma: no cover
    main()
