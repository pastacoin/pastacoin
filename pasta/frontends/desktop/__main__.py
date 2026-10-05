"""Launch The Pasta Machine: ``python -m pasta.frontends.desktop``."""
import sys

try:
    from pasta.frontends.desktop.app import main
except ImportError as exc:  # pragma: no cover - optional dependency
    print(f"The desktop app needs PySide6 ({exc}). Install it with: pip install PySide6")
    sys.exit(1)

if __name__ == "__main__":  # pragma: no cover
    main()
