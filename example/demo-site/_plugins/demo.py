"""Example plugin exercising every lanyon hook. See lanyon/plugins.py for the
full hook API - this file only needs to define the ones it uses."""
import datetime


def before_build(site):
    site = dict(site)
    site["build_year"] = datetime.date.today().year
    return site


def register_filters(env):
    env.filters["shout"] = lambda s: str(s).upper() + "!"


def before_render(site, page, body, path):
    if path.name == "index.html":
        body = body.replace("Welcome to", "Hello from a plugin,")
        return page, body
    return None


def after_render(site, page, rendered, path):
    if path.suffix == ".html":
        return rendered + f"\n<!-- built {site.get('build_year')} -->\n"
    return None


def after_build(site, out_root):
    (out_root / "sitemap.txt").write_text(
        "\n".join(sorted(p.name for p in out_root.glob("*") if p.is_file())),
        encoding="utf-8",
    )
