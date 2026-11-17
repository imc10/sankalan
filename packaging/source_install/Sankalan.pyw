# Starts Sankalan from source with pythonw.exe (no console window). Development fallback only (see README.txt).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sankalan.__main__ import main  # noqa: E402

if __name__ == "__main__":         # reader workers re-import this file under spawn; only the parent runs main()
    sys.exit(main())
