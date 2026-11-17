"""Entry point: ``python -m sankalan`` / ``Sankalan.exe`` opens the window.

Reader workers are this same program started again in worker mode (spawn), so ``freeze_support()`` runs first: in
the packaged exe it turns a worker start into the worker and never reaches the window (T5, Packaging).

    --version                       print "Sankalan <version>"
    --self-test [--report <json>]   smoke test in a temporary folder (``sankalan.selftest``); exit 0 = passed
    --remove-data                   used by the uninstaller when the user chose to delete the data (T26)
"""
import multiprocessing
import sys


def main(argv=None) -> int:
    multiprocessing.freeze_support()
    args = list(sys.argv[1:] if argv is None else argv)
    if "--version" in args:
        from sankalan import APP_NAME, __version__
        print(f"{APP_NAME} {__version__}")
        return 0
    if "--self-test" in args:
        from sankalan.selftest import run_self_test
        return run_self_test(args)
    if "--remove-data" in args:
        from sankalan.uninstall import remove_data
        return remove_data()
    from sankalan.app import run
    return run([sys.argv[0], *args])


if __name__ == "__main__":
    sys.exit(main())
