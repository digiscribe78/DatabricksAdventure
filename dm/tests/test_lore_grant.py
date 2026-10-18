"""Rebuilding the lore index drops its grants, so every ingest re-grants the DM's SELECT."""

from devtools.lore_grant import lore_grant_statement, regrant

SP = "11111111-2222-3333-4444-555555555555"


def test_the_dm_gets_select_on_the_rebuilt_index():
    assert lore_grant_statement(SP, "cat", "sch") == f"GRANT SELECT ON TABLE `cat`.`sch`.`lore_index` TO `{SP}`"


def test_regrant_applies_it_for_the_deployed_dm():
    applied = []
    assert regrant("cat", "sch", find_sp=lambda: SP, apply=lambda stmts: applied.extend(stmts) or []) == 0
    assert applied == [lore_grant_statement(SP, "cat", "sch")]


def test_before_the_dm_exists_there_is_nothing_to_grant_yet():
    applied = []
    assert regrant("cat", "sch", find_sp=lambda: None, apply=lambda stmts: applied.extend(stmts) or []) == 0
    assert applied == []  # make deploy grants it later, in deploy-agent


def test_a_failed_grant_fails_the_ingest_loudly():
    assert regrant("cat", "sch", find_sp=lambda: SP, apply=lambda stmts: ["GRANT …: PERMISSION_DENIED"]) == 1
