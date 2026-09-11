"""Minimal dev HTTP server for the build output directory."""
import functools
import http.server


def serve_dir(out_dir: str, host: str = "127.0.0.1", port: int = 8000) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=out_dir)
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"serving {out_dir} at http://{host}:{port}/")
        httpd.serve_forever()
