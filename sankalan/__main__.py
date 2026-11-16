"""Entry point. Worker and self-test modes, and the window, arrive in later phases."""
import multiprocessing
import sys

from sankalan import APP_NAME, __version__


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    print(f"{APP_NAME} {__version__}: version 2 is being built; there is no window yet.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
