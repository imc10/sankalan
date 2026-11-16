# Starts Sankalan from source with pythonw.exe (no console window).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sankalan.ui.app import main  # noqa: E402

sys.exit(main())
