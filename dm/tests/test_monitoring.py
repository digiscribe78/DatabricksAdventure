"""Live monitoring: the evals' judges registered on the play traces, sampled."""

from types import SimpleNamespace

from devtools.monitoring import JUDGES, ensure_judges, stop_all


class FakeScorer:
    def __init__(self, name, log):
        self.name, self.log = name, log

    def register(self, *, name=None, experiment_id=None):
        self.log.append(("register", name, experiment_id))
        return self

    def start(self, *, name=None, experiment_id=None, sampling_config=None):
        self.log.append(("start", self.name, sampling_config.sample_rate))
        return self

    def update(self, *, name=None, experiment_id=None, sampling_config=None):
        self.log.append(("update", self.name, sampling_config.sample_rate))
        return self

    def stop(self, *, name=None, experiment_id=None):
        self.log.append(("stop", self.name))
        return self


def registry(existing, log):
    return SimpleNamespace(list_scorers=lambda experiment_id: [FakeScorer(n, log) for n in existing],
                           get_scorer=lambda name, experiment_id: FakeScorer(name, log))


def test_the_live_judges_match_the_evals_and_are_sampled():
    assert [(name, rate) for name, _, rate in JUDGES] == [("safety", 1.0), ("in_character", 0.25), ("player_agency", 0.25)]


def test_new_judges_are_registered_and_started(monkeypatch):
    log = []
    monkeypatch.setattr("devtools.monitoring.JUDGES", [(n, FakeScorer(n, log), r) for n, _, r in JUDGES])
    ensure_judges("exp-1", registry([], log))
    assert ("register", "safety", "exp-1") in log and ("start", "safety", 1.0) in log
    assert ("start", "player_agency", 0.25) in log


def test_existing_judges_are_updated_not_registered_twice(monkeypatch):
    log = []
    monkeypatch.setattr("devtools.monitoring.JUDGES", [(n, FakeScorer(n, log), r) for n, _, r in JUDGES])
    ensure_judges("exp-1", registry(["safety"], log))
    assert ("update", "safety", 1.0) in log and ("register", "safety", "exp-1") not in log
    assert ("register", "in_character", "exp-1") in log


def test_stop_pauses_every_judge_without_deleting():
    log = []
    stop_all("exp-1", registry(["safety", "in_character"], log))
    assert log == [("stop", "safety"), ("stop", "in_character")]
