import subprocess
import shutil
import os
from pathlib import Path


def graphify_available():
    """Return True if the `graphify` CLI or `graphifyy` package is available."""
    return shutil.which("graphify") is not None


def run_graphify(path, out_dir=None, extra_args=None):
    """Run the graphify CLI on `path` and return (success, output_file_or_error).

    This wrapper prefers the CLI `graphify` command. If not installed, it will attempt
    to call the package entrypoint via `python -m graphify`.
    """
    extra_args = extra_args or []
    path = str(path)
    out_dir = out_dir or (str(Path(path).resolve()) + "-graphify-out")
    cmd = None
    if shutil.which("graphify"):
        cmd = ["graphify", path, "--svg", "--out", out_dir] + extra_args
    else:
        # try python -m graphify (works if package installed)
        cmd = [os.sys.executable, "-m", "graphify", path, "--svg", "--out", out_dir] + extra_args

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode == 0:
            svg_path = os.path.join(out_dir, "graph.svg")
            if os.path.exists(svg_path):
                return True, svg_path
            # fallback: return out_dir
            return True, out_dir
        else:
            return False, proc.stderr or proc.stdout
    except Exception as e:
        return False, str(e)
