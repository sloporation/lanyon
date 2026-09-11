import argparse
import sys
import threading

from .serve import serve_dir
from .site import build_site
from .watch import watch_and_build


def main() -> None:
    # Force line-buffered stdout. Without this, build/watch/serve logging
    # (print()) sits in Python's default block buffer whenever stdout isn't
    # a TTY - e.g. piped through Docker's log driver - so logs appear late
    # or not at all until the process exits. PYTHONUNBUFFERED alone isn't
    # reliably honoured by the PyInstaller-frozen binary, so set it here in
    # code instead.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    parser = argparse.ArgumentParser(
        prog="lanyon",
        description="A freeform, Liquid-templated static site generator.",
    )
    parser.add_argument("-i", "--input", required=True, metavar="SRCDIR", help="source directory")
    parser.add_argument("-o", "--output", required=True, metavar="BUILDDIR", help="output/build directory")
    parser.add_argument(
        "-I", "--incremental", action="store_true",
        help="only rebuild files that changed since the last build",
    )
    parser.add_argument(
        "--cache-file", metavar="PATH",
        help=(
            "where the incremental-build cache lives (default: SRCDIR/.lanyon-cache.json). "
            "Point this at a path outside SRCDIR for a cache that's ephemeral by default "
            "(e.g. lives only inside a container), or at a path you mount/back up to "
            "preserve it across runs."
        ),
    )
    parser.add_argument(
        "-w", "--watch", action="store_true",
        help="watch SRCDIR and rebuild on changes (implies --incremental)",
    )
    parser.add_argument(
        "-s", "--serve", action="store_true",
        help="serve BUILDDIR over HTTP for local dev testing",
    )
    parser.add_argument("--host", default="127.0.0.1", help="dev server bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="dev server port (default: 8000)")
    args = parser.parse_args()

    try:
        if args.watch:
            if args.serve:
                thread = threading.Thread(
                    target=serve_dir, args=(args.output, args.host, args.port), daemon=True,
                )
                thread.start()
            try:
                watch_and_build(args.input, args.output, cache_file=args.cache_file)
            except KeyboardInterrupt:
                print("stopped watching")
        elif args.serve:
            build_site(args.input, args.output, incremental=args.incremental, cache_file=args.cache_file)
            try:
                serve_dir(args.output, args.host, args.port)
            except KeyboardInterrupt:
                print("server stopped")
        else:
            build_site(args.input, args.output, incremental=args.incremental, cache_file=args.cache_file)
    except Exception as exc:  # noqa: BLE001 - top-level CLI error boundary
        print(f"lanyon: error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
