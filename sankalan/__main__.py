"""Entry point: ``python -m sankalan`` opens the window. Reader workers are started with spawn, so
``freeze_support()`` must run first in the packaged exe. The self-test mode arrives in Phase 9/11."""
import multiprocessing
import sys


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        from sankalan import APP_NAME, __version__
        print(f"{APP_NAME} {__version__}")
        return 0
    from sankalan.app import run
    return run([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
