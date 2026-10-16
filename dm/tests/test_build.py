import subprocess
import sys
from pathlib import Path

import yaml
from devtools.build import EXCLUDES, copy_source, render_app_yaml


def test_render_app_yaml_adds_and_replaces_env():
    base = "command: [uv, run, start-server]\nenv:\n  - name: KEEP\n    value: a\n  - name: SWAP\n    valueFrom: x\n"
    out = yaml.safe_load(render_app_yaml(base, {"SWAP": "b", "NEW": "c"}))
    assert out["command"] == ["uv", "run", "start-server"]
    assert out["env"] == [{"name": "KEEP", "value": "a"}, {"name": "SWAP", "value": "b"}, {"name": "NEW", "value": "c"}]


def test_render_app_yaml_without_env_section():
    out = yaml.safe_load(render_app_yaml('command: ["uv", "run", "start-server"]\n', {"A": "1"}))
    assert out["env"] == [{"name": "A", "value": "1"}]


def test_copy_source_excludes_local_state(tmp_path):
    src = tmp_path / "src"
    for rel in ["app.yaml", "agent/agent.py", ".env", ".venv/x", ".databricks/sync.json",
                "agent/__pycache__/a.pyc", ".agentbricks/project.toml", ".agentbricks/mlflow.db"]:
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text("x")
    dst = tmp_path / "dst"
    (dst / "stale").mkdir(parents=True)
    copy_source(src, dst)
    copied = sorted(str(p.relative_to(dst)) for p in dst.rglob("*") if p.is_file())
    assert copied == [".agentbricks/project.toml", "agent/agent.py", "app.yaml"]
    assert ".databricks" in EXCLUDES


def test_cli_copies_and_renders(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.yaml").write_text("command: [x]\n")
    dst = tmp_path / "dst"
    subprocess.run([sys.executable, "-m", "devtools.build", str(src), str(dst), "LORE_INDEX=c.s.i"],
                   cwd=Path(__file__).resolve().parents[1], check=True)
    assert yaml.safe_load((dst / "app.yaml").read_text())["env"] == [{"name": "LORE_INDEX", "value": "c.s.i"}]
