from typing import List
from rules.base_rule import Rule


class RuleLoader:

    @staticmethod
    def load_common_rules() -> List[Rule]:
        from rules.common.grammar import create_grammar_rule
        from rules.common.format import create_format_rule

        rules: List[Rule] = []

        # format 是单个规则
        rules.append(create_format_rule())

        # grammar 是单个规则
        rules.append(create_grammar_rule())

        return rules

    @staticmethod
    def load_aviation_rules() -> List[Rule]:
        from rules.aviation.actuator_rules import create_actuator_rules
        return create_actuator_rules()

    @staticmethod
    def load_extension_rules() -> List[Rule]:
        """加载扩展贡献的规则。"""
        from extensions.discovery import collect_from_extensions
        return collect_from_extensions("register_rules")

    @staticmethod
    def load_all_rules(profile: str = "default", include_extensions: bool = True) -> List[Rule]:
        rules: List[Rule] = []

        # 1. 通用规则
        rules.extend(RuleLoader.load_common_rules())

        # 2. 行业规则
        profile_map = {
            "aviation": RuleLoader.load_aviation_rules,
        }

        if profile in profile_map:
            rules.extend(profile_map[profile]())

        # 3. 扩展规则
        if include_extensions:
            rules.extend(RuleLoader.load_extension_rules())

        # 4. 应用用户覆盖
        from config.rule_overrides import apply_overrides
        rules = apply_overrides(rules)

        return rules