"""Build a clean deploy copy of the DM project.

agentbricks deploy rewrites app.yaml and agent.toml with workspace-specific values, and its source
sync honours .gitignore and incremental .databricks state. So we deploy from a fresh copy outside
the repo, with our env rendered into app.yaml.
"""

import shutil
import sys
from pathlib import Path

import yaml

EXCLUDES = (".venv", ".env", ".databricks", "__pycache__", ".pytest_cache", ".ruff_cache",
            "mlflow.db*", "app.agentbricksdev.yaml")


def copy_source(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXCLUDES))


def render_app_yaml(text: str, env: dict[str, str]) -> str:
    doc = yaml.safe_load(text) or {}
    entries = [e for e in doc.get("env") or [] if isinstance(e, dict)]
    by_name = {e.get("name"): e for e in entries}
    for name, value in env.items():
        if name in by_name:
            by_name[name].pop("valueFrom", None)
            by_name[name]["value"] = value
        else:
            entries.append({"name": name, "value": value})
    doc["env"] = entries
    return yaml.safe_dump(doc, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print("usage: python -m devtools.build <src> <dst> [KEY=VALUE ...]", file=sys.stderr)
        return 2
    src, dst = Path(args[0]), Path(args[1])
    env = dict(a.split("=", 1) for a in args[2:])
    copy_source(src, dst)
    app_yaml = dst / "app.yaml"
    app_yaml.write_text(render_app_yaml(app_yaml.read_text(), env))
    print(f"built {dst} with env {sorted(env)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
