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
    def load_all_rules(profile: str = "default") -> List[Rule]:
        rules: List[Rule] = []

        # 1️⃣ 通用规则
        rules.extend(RuleLoader.load_common_rules())

        # 2️⃣ 行业规则（可扩展）
        profile_map = {
            "aviation": RuleLoader.load_aviation_rules,
            # 未来可以扩展：
            # "space": load_space_rules,
            # "aircraft": load_aircraft_rules
        }

        if profile in profile_map:
            rules.extend(profile_map[profile]())

        return rules