"""Core build logic: walks srcdir, applies Liquid templating, layouts, includes."""
import json
import shutil
from pathlib import Path

from liquid import Environment
from liquid import FileSystemLoader

from .config import load_site_config
from .frontmatter import parse_front_matter
from .plugins import (
    PLUGINS_DIR_NAME,
    load_plugins,
    run_after_build,
    run_after_render,
    run_before_build,
    run_before_render,
    run_register_filters,
)

LAYOUTS_DIR_NAME = "_layouts"
INCLUDES_DIR_NAME = "_includes"
CONFIG_FILE_NAME = "_config.yml"
CACHE_FILE_NAME = ".lanyon-cache.json"

MAX_LAYOUT_DEPTH = 10


def is_excluded(path: Path, src_root: Path) -> bool:
    """Anything under a dir/file starting with `_` or `.` is not published directly.

    This is how _config.yml, _layouts/, _includes/, and any user-defined
    "private" folders (e.g. _drafts/) stay out of the output. It also keeps
    lanyon's own incremental-build cache file (.lanyon-cache.json) out of the
    build.
    """
    for part in path.relative_to(src_root).parts:
        if part.startswith("_") or part.startswith("."):
            return True
    return False


def _is_special(rel: str) -> bool:
    """True for files that can affect *other* pages: config, layouts, includes, plugins.

    A change to any of these invalidates the incremental cache entirely,
    since we don't track which pages depend on which layout/include, and a
    plugin hook can touch anything.
    """
    if rel == CONFIG_FILE_NAME:
        return True
    head = rel.split("/", 1)[0]
    return head in (LAYOUTS_DIR_NAME, INCLUDES_DIR_NAME, PLUGINS_DIR_NAME)


def resolve_layout_path(layouts_dir: Path, layout_name: str) -> Path | None:
    candidate = layouts_dir / layout_name
    if candidate.exists():
        return candidate
    # Allow `layout: default` to match `_layouts/default.html` etc.
    matches = list(layouts_dir.glob(f"{layout_name}.*"))
    return matches[0] if matches else None


def apply_layouts(env: Environment, layouts_dir: Path, content: str, layout_name: str, site: dict, page: dict) -> str:
    depth = 0
    while layout_name and depth < MAX_LAYOUT_DEPTH:
        layout_path = resolve_layout_path(layouts_dir, layout_name)
        if layout_path is None:
            print(f"WARNING: layout '{layout_name}' not found in {layouts_dir}, skipping")
            break

        raw = layout_path.read_text(encoding="utf-8")
        layout_fm, layout_body = parse_front_matter(raw)

        template = env.from_string(layout_body)
        content = template.render(site=site, page=page, layout=layout_fm, content=content)

        layout_name = layout_fm.get("layout")
        depth += 1

    if depth >= MAX_LAYOUT_DEPTH:
        print(f"WARNING: layout chain exceeded {MAX_LAYOUT_DEPTH} levels, possible cycle - stopped")

    return content


def default_cache_path(src_root: Path) -> Path:
    return src_root / CACHE_FILE_NAME


def _load_cache(cache_path: Path) -> dict:
    if not cache_path.exists():
        return {}
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache_path: Path, state: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(state), encoding="utf-8")


def _render_file(env: Environment, layouts_dir: Path, site: dict, path: Path, out_path: Path, plugins: list) -> None:
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, ValueError):
        # Binary file (image, font, etc.) - pass through untouched.
        shutil.copy2(path, out_path)
        print(f"copied  {out_path.name}")
        return

    front_matter, body = parse_front_matter(raw)
    front_matter, body = run_before_render(plugins, site, front_matter, body, path)

    try:
        template = env.from_string(body)
        rendered = template.render(site=site, page=front_matter)
    except Exception as exc:  # noqa: BLE001 - surface template errors, keep building
        print(f"WARNING: template error in {path}: {exc}")
        rendered = body

    layout_name = front_matter.get("layout")
    if layout_name:
        if layouts_dir.exists():
            rendered = apply_layouts(env, layouts_dir, rendered, layout_name, site, front_matter)
        else:
            print(f"WARNING: {path} sets layout '{layout_name}' but {LAYOUTS_DIR_NAME}/ does not exist")

    rendered = run_after_render(plugins, site, front_matter, rendered, path)

    out_path.write_text(rendered, encoding="utf-8")


def build_site(src_dir: str, out_dir: str, incremental: bool = False, cache_file: str | None = None) -> None:
    """Build the site.

    With incremental=False (the default), every publishable file is
    re-rendered on every run - this is the original, simplest-possible
    behaviour.

    With incremental=True, lanyon keeps a small cache
    (`<srcdir>/.lanyon-cache.json`, itself excluded from the build) of each
    source file's mtime/size. On the next incremental build, only files that
    are new or changed since the cache was written are re-rendered, and
    files removed from the source tree are removed from the output. Any
    change to `_config.yml`, `_layouts/`, `_includes/`, or `_plugins/` forces
    a full rebuild, since lanyon doesn't track which pages depend on which
    layout/include, and a plugin hook can touch anything.

    Plugins: any `.py` file under `srcdir/_plugins/` is loaded and its hooks
    run at the appropriate points (see lanyon/plugins.py for the hook API).
    """
    src_root = Path(src_dir).resolve()
    out_root = Path(out_dir).resolve()

    if not src_root.is_dir():
        raise NotADirectoryError(f"Source directory not found: {src_root}")

    out_root.mkdir(parents=True, exist_ok=True)

    cache_path = Path(cache_file).resolve() if cache_file else default_cache_path(src_root)

    plugins = load_plugins(src_root)

    site = load_site_config(src_root)
    site = run_before_build(plugins, site)

    includes_dir = src_root / INCLUDES_DIR_NAME
    layouts_dir = src_root / LAYOUTS_DIR_NAME

    loader = FileSystemLoader(str(includes_dir)) if includes_dir.exists() else None
    env = Environment(loader=loader)
    run_register_filters(plugins, env)

    all_paths = [
        p for p in sorted(src_root.rglob("*"))
        if p.is_file() and p.resolve() != cache_path
    ]

    new_state = {}
    for path in all_paths:
        rel = str(path.relative_to(src_root))
        st = path.stat()
        new_state[rel] = [st.st_mtime_ns, st.st_size]

    old_state = _load_cache(cache_path) if incremental else {}

    full_rebuild = not incremental or not old_state
    if incremental and old_state:
        all_special = {rel for rel in set(old_state) | set(new_state) if _is_special(rel)}
        for rel in all_special:
            if old_state.get(rel) != new_state.get(rel):
                full_rebuild = True
                break

    written = 0
    skipped = 0
    for path in all_paths:
        rel_path = path.relative_to(src_root)
        rel = str(rel_path)
        if is_excluded(path, src_root):
            continue

        if not full_rebuild and old_state.get(rel) == new_state.get(rel):
            skipped += 1
            continue

        out_path = out_root / rel_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        _render_file(env, layouts_dir, site, path, out_path, plugins)
        print(f"wrote   {rel}")
        written += 1

    removed = 0
    if not full_rebuild:
        for rel in set(old_state) - set(new_state):
            if _is_special(rel) or any(part.startswith("_") or part.startswith(".") for part in Path(rel).parts):
                continue
            out_path = out_root / rel
            if out_path.exists():
                out_path.unlink()
                print(f"removed {rel}")
                removed += 1

    if incremental:
        _save_cache(cache_path, new_state)
        print(f"incremental build: {written} written, {skipped} unchanged, {removed} removed"
              + (" (full rebuild - config/layout/include/plugin changed)" if full_rebuild else ""))

    run_after_build(plugins, site, out_root)
