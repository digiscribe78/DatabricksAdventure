import mlflow
import pytest


@pytest.fixture
def local_mlflow(tmp_path, monkeypatch):
    """A throwaway local MLflow store, so tracing and evaluation tests never touch a workspace."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    # Write traces synchronously, so a test can read back the trace it just made.
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    mlflow.set_experiment("tests")
    yield
