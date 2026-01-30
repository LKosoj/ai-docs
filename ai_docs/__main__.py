import importlib
import os
import sys


def _load_main():
    try:
        from .cli import main
        return main
    except ImportError:
        # Fallback when executed as a script (e.g., `python ai_docs ...`)
        pkg_dir = os.path.dirname(os.path.abspath(__file__))
        parent = os.path.dirname(pkg_dir)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        return importlib.import_module("ai_docs.cli").main


main = _load_main()

if __name__ == "__main__":
    main()
