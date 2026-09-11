# lanyon

A freeform, Liquid-templated static site generator. It doesn't enforce a
content model — it walks a source directory, runs every file through
Liquid, and writes it out with the same relative path and extension.

## Usage

```
lanyon -i srcdir/ -o builddir/
```

### Incremental builds

```
lanyon -i srcdir/ -o builddir/ -I
```

`-I`/`--incremental` keeps a small cache of each source file's mtime/size
and only re-renders files that are new or changed since the last
incremental build; files removed from srcdir are removed from builddir
too. Any change to `_config.yml`, `_layouts/`, or `_includes/` forces a
full rebuild, since lanyon doesn't track which pages depend on which
layout/include. Without `-I`, every run is a full rebuild (the original
behaviour).

By default the cache lives at `srcdir/.lanyon-cache.json` (itself excluded
from the build, like any dotfile), so it persists on disk between runs
same as everything else in srcdir. Override its location with
`--cache-file PATH` - point it outside srcdir to keep srcdir untouched
(e.g. so it can stay read-only, or so the cache is ephemeral by default
in a container), or at a path you deliberately mount/back up to preserve
it on purpose.

### Watch mode

```
lanyon -i srcdir/ -o builddir/ -w
```

`-w`/`--watch` builds once, then polls srcdir and rebuilds (incrementally)
whenever a file changes, until interrupted with Ctrl-C.

### Dev server

```
lanyon -i srcdir/ -o builddir/ -w -s
```

`-s`/`--serve` serves builddir over HTTP (default `http://127.0.0.1:8000/`,
override with `--host`/`--port`). Combine it with `-w` for live-reloading
local dev: edit a file, refresh the browser, see the change. `-s` on its
own (without `-w`) just builds once and serves the result.

## Plugins

Any `.py` file under `srcdir/_plugins/` is loaded and run at build time -
no recompilation, even for the compiled binary, since it still contains a
full Python interpreter and just `importlib`s the file off disk (the same
way discord.py loads cogs). A plugin is a plain module defining any of
these optional top-level functions; lanyon calls whichever ones exist, on
every plugin, in filename order:

```
before_build(site: dict) -> dict | None
register_filters(env: liquid.Environment) -> None
before_render(site: dict, page: dict, body: str, path: Path) -> tuple[dict, str] | None
after_render(site: dict, page: dict, rendered: str, path: Path) -> str | None
after_build(site: dict, out_root: Path) -> None
```

- `before_build` runs once, after `_config.yml` is loaded - return a dict
  to replace `site`.
- `register_filters` runs once, after the Liquid environment is created -
  register custom filters/tags on it directly (see python-liquid's docs).
- `before_render`/`after_render` run per file, before/after templating and
  layout application - return a value to override, or `None` to leave it
  as-is.
- `after_build` runs once, after every file is written - write whatever
  else you want (a sitemap, an RSS feed, ...) under `out_root`, which
  already holds every published page, changed or not.

See `example/demo-site/_plugins/demo.py` for a plugin exercising all
five. Full docs/rationale in `lanyon/plugins.py`.

A plugin can only import the standard library plus what lanyon itself
bundles (`python-liquid`, `PyYAML`) - the compiled binary has no `pip`
inside it to fetch anything else at runtime. A broken plugin (raises on
load or from a hook) is skipped with a warning rather than failing the
build. Plugins run with the same permissions as lanyon itself and are not
sandboxed - only use ones you trust. Like `_layouts/`/`_includes/`, any
change under `_plugins/` forces a full rebuild in incremental mode, since
a hook can affect any page.

## Source directory conventions

- `_config.yml` — site-wide variables, exposed to every template as `site`
  (e.g. `name: asd` in the file becomes `{{ site.name }}`).
- `_layouts/` — optional. A file sets `layout: default` in its front matter
  to be wrapped by `_layouts/default.*`. Layouts insert the page via
  `{{ content }}` and can themselves chain to another layout.
- `_includes/` — optional. Available to any template via
  `{% include "header.html" %}`.
- Anything else — templated as-is and written to the output with the same
  relative path/extension. A `.php` file stays a `.php` file; a `.txt` stays
  a `.txt`. No file type is treated specially.
- YAML front matter (`---` delimited block at the top of a file) is
  optional per file. If present, its keys are exposed as `page` in that
  file's template (and layout), and `layout:` is read from it. If absent,
  the file is still templated with `site` available — it just isn't
  wrapped in a layout.
- Any file or directory whose name starts with `_` or `.` is excluded from
  the output (this is how `_config.yml`, `_layouts/`, `_includes/`, and any
  private folder you create, e.g. `_drafts/`, stay out of the build).
- Files that aren't valid UTF-8 text (images, fonts, etc.) are copied
  through unchanged rather than templated.

## Project layout

```
src/
  lanyon/
    cli.py          # argument parsing, entry point
    config.py       # loads _config.yml
    frontmatter.py  # YAML front matter parsing
    site.py         # walks srcdir, applies templating/layouts/includes,
                    #   incremental-build caching
    watch.py        # polls srcdir and rebuilds on change
    serve.py        # dev HTTP server for builddir
  lanyon_entry.py    # PyInstaller entry point
build.sh            # produces the single-file `lanyon` binary
docker/
  Dockerfile              # reproducible PyInstaller build, minimal runtime image
  Dockerfile.dockerignore # build-context excludes for the above
  docker-compose.yml      # incremental/watch/dev-server workflow
example/demo-site/  # minimal working example (config, layout, include,
                    # front-matter page, and a plain .php/.txt file)
```

## Development

```
pip install -e .
python3 -m lanyon.cli -i example/demo-site -o /tmp/out
```

## Building the single-file binary

```
./build.sh
sudo cp dist/lanyon /usr/bin/lanyon
```

### With Docker

`docker/Dockerfile` does the same PyInstaller build inside a container, so
you get a reproducible Linux binary without installing Python/PyInstaller
locally. Build it from the repo root (the build context, since the
Dockerfile COPYs `src/`):

```
docker build -f docker/Dockerfile -t lanyon .
docker run --rm -v "$PWD/example/demo-site:/site/src:ro" \
  -v "$PWD/build:/site/build" lanyon -i /site/src -o /site/build
```

The final image contains only the compiled binary (no Python, no pip
packages), so running it is a faithful test of what end users get.

For local dev — live rebuild + a dev server, no local install at all, run
from `docker/` (relative paths and SRC/OUT overrides resolve from there):

```
cd docker && docker compose up --build
```

serves `http://localhost:8000/`, watching `example/demo-site` by default.
Point it at your own site with `SRC=../my-site docker compose up`, or run a
one-shot build with `docker compose run --rm lanyon -i /site/src -o /site/build`.

SRCDIR is mounted read-only and the incremental cache lives inside the
container at `/var/cache/lanyon/cache.json` (not on a volume), so by
default it's ephemeral - a fresh container starts with a full rebuild, and
nothing lanyon-related is written to your source tree. To keep the cache
warm across `docker compose down`/`up` instead, uncomment the
`lanyon-cache` volume in `docker-compose.yml`.

This uses PyInstaller rather than Nuitka: it needs no C compiler on the
build machine, so it's the lower-friction path to "no dependencies for the
end user." Trade-off: it must be run once per target OS/arch (Linux, macOS,
Windows) — no cross-compiling — and startup is a touch slower than a true
compiled binary. If that startup cost ever matters, Nuitka is the drop-in
alternative later; nothing in the code depends on the packaging choice.

## Known gaps / not yet built

- No `_posts`/collections, no pagination.
- No `_data/` folder for structured non-page data.
- No asset pipeline (Sass, bundling, etc.) — freeform files pass through
  Liquid only.
- Watch mode polls (default every 0.5s) rather than using OS file-change
  notifications, to keep the single-file binary dependency-free.
- Incremental builds invalidate the whole cache (full rebuild) on any
  `_config.yml`/`_layouts/`/`_includes/` change, rather than tracking
  per-page dependencies.
