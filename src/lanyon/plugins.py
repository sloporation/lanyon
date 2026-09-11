"""Plugin loading: srcdir/_plugins/*.py, dynamically imported at build time.

Mirrors discord.py's cog-loading model: lanyon itself never changes - a
single build (and, for the distributed release, a single compiled binary)
loads whatever plugin files it finds on disk at runtime. A plugin is a
plain Python module that defines any of a handful of optional top-level
functions (hooks); lanyon calls whichever ones exist, on every plugin, in
filename order.

Hooks (all optional - define only the ones you need):

    before_build(site: dict) -> dict | None
        Called once, after _config.yml is loaded. Return a dict to replace
        `site` for the rest of the build, or None to leave it as-is.

    register_filters(env: liquid.Environment) -> None
        Called once, after the Liquid environment is created. Register
        custom filters/tags on `env` directly - see python-liquid's own
        docs (e.g. `env.filters["slugify"] = my_slugify`).

    before_render(site: dict, page: dict, body: str, path: Path) -> tuple[dict, str] | None
        Called per file, before Liquid rendering. Return (page, body) to
        override front matter/content for this file, or None to leave
        them as-is.

    after_render(site: dict, page: dict, rendered: str, path: Path) -> str | None
        Called per file, after Liquid rendering and layout application,
        just before the file is written. Return a string to override the
        output, or None to leave it as-is.

    after_build(site: dict, out_root: Path) -> None
        Called once, after every file is written. Write whatever else you
        want (a sitemap, an RSS feed, ...) directly under out_root - it
        already contains every published page, changed or not.

A plugin can only import the standard library plus whatever lanyon itself
already bundles (python-liquid, PyYAML): the compiled `lanyon` binary has
no `pip` inside it to fetch anything else at runtime. A broken plugin
(raises on load, or raises from a hook) is skipped with a warning rather
than failing the whole build - one bad plugin shouldn't take down the
site.

Plugins run with the same permissions as lanyon itself and are not
sandboxed. Only use plugins you trust.
"""
import importlib.util
from pathlib import Path
from types import ModuleType

PLUGINS_DIR_NAME = "_plugins"


def load_plugins(src_root: Path) -> list[ModuleType]:
    plugins_dir = src_root / PLUGINS_DIR_NAME
    if not plugins_dir.is_dir():
        return []

    modules = []
    for path in sorted(plugins_dir.glob("*.py")):
        spec = importlib.util.spec_from_file_location(f"lanyon_plugin.{path.stem}", path)
        if spec is None or spec.loader is None:
            print(f"WARNING: could not load plugin {path}, skipping")
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 - a broken plugin shouldn't crash the build
            print(f"WARNING: plugin {path} raised on load: {exc}, skipping")
            continue
        modules.append(module)
        print(f"plugin  {path.relative_to(src_root)}")

    return modules


def _call(plugin: ModuleType, hook_name: str, *args):
    hook = getattr(plugin, hook_name, None)
    if hook is None:
        return None
    try:
        return hook(*args)
    except Exception as exc:  # noqa: BLE001 - a broken hook shouldn't crash the build
        print(f"WARNING: plugin {plugin.__name__} hook {hook_name} raised: {exc}, ignoring")
        return None


def run_before_build(plugins: list[ModuleType], site: dict) -> dict:
    for plugin in plugins:
        result = _call(plugin, "before_build", site)
        if result is not None:
            site = result
    return site


def run_register_filters(plugins: list[ModuleType], env) -> None:
    for plugin in plugins:
        _call(plugin, "register_filters", env)


def run_before_render(plugins: list[ModuleType], site: dict, page: dict, body: str, path: Path) -> tuple[dict, str]:
    for plugin in plugins:
        result = _call(plugin, "before_render", site, page, body, path)
        if result is not None:
            page, body = result
    return page, body


def run_after_render(plugins: list[ModuleType], site: dict, page: dict, rendered: str, path: Path) -> str:
    for plugin in plugins:
        result = _call(plugin, "after_render", site, page, rendered, path)
        if result is not None:
            rendered = result
    return rendered


def run_after_build(plugins: list[ModuleType], site: dict, out_root: Path) -> None:
    for plugin in plugins:
        _call(plugin, "after_build", site, out_root)
