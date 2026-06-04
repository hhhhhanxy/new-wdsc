from rules.loaders.rule_loader import RuleLoader


def test_custom_rule_identity_uses_canonical_rule_id_with_aliases():
    rules = RuleLoader.load_all_rules("default", include_extensions=False)
    by_id = {rule.rule_id: rule for rule in rules}

    assert "rule_p_001" in by_id
    assert "任务来源检查" not in by_id

    task_source_rule = by_id["rule_p_001"]
    assert task_source_rule.code == "P-001"
    assert "任务来源检查" in task_source_rule.aliases
    assert "P-001" in task_source_rule.aliases
