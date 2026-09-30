"""
Application entry point.
"""

import os
import sys


# --- Tcl/Tk paths inside .app (for py2app) ---
if getattr(sys, "frozen", False):
    resources = os.path.join(os.path.dirname(sys.executable), "..", "Resources")
    resources = os.path.abspath(resources)
    lib_dir = os.path.join(resources, "lib")

    tcl_dir = os.path.join(lib_dir, "tcl9.0")
    tk_dir = os.path.join(lib_dir, "tk9.0")

    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir

# --- Application ---
from app.ui.main_window import MainWindow


def main():
    app = MainWindow()
    app.run()


if __name__ == "__main__":
    main()
