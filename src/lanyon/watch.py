"""Watch mode: rebuild the site whenever a file under srcdir changes."""
import time
from pathlib import Path

from .site import build_site, default_cache_path


def _snapshot(src_root: Path, cache_path: Path) -> dict:
    state = {}
    for path in src_root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve() == cache_path:
            # Every build (incremental=True) rewrites the cache file, so
            # including it here (when it happens to live under srcdir)
            # would make the watcher detect its own writes as a source
            # change and rebuild forever.
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        state[str(path.relative_to(src_root))] = (st.st_mtime_ns, st.st_size)
    return state


def watch_and_build(src_dir: str, out_dir: str, poll_interval: float = 0.5, cache_file: str | None = None) -> None:
    """Build once, then poll srcdir and rebuild (incrementally) on any change.

    Polling rather than an OS file-watcher keeps this dependency-free, which
    matters for a tool that ships as a single self-contained binary.
    """
    src_root = Path(src_dir).resolve()
    cache_path = Path(cache_file).resolve() if cache_file else default_cache_path(src_root)

    build_site(src_dir, out_dir, incremental=True, cache_file=cache_file)
    last_state = _snapshot(src_root, cache_path)
    print(f"watching {src_root} for changes (ctrl-c to stop)")

    while True:
        time.sleep(poll_interval)
        state = _snapshot(src_root, cache_path)
        if state == last_state:
            continue
        last_state = state
        print("change detected, rebuilding...")
        try:
            build_site(src_dir, out_dir, incremental=True, cache_file=cache_file)
        except Exception as exc:  # noqa: BLE001 - keep watching after a bad build
            print(f"lanyon: error: {exc}")
