"""
统一扩展注册中心。
"""
import logging
from typing import List, Dict, Optional

from rules.base_rule import Rule
from extensions.discovery import collect_from_extensions

logger = logging.getLogger(__name__)


class ExtensionRegistry:
    """
    扩展注册中心：
    1. 自动发现 extensions/ 目录下的扩展模块
    2. 注册其贡献（规则、生成器等）
    3. 提供查询接口
    """

    def __init__(self):
        self._rules: List[Rule] = []
        self._generators: Dict[str, object] = {}
        self._loaded = False

    def load_extensions(self):
        """发现并注册所有扩展。幂等操作。"""
        if self._loaded:
            return self

        discovered_rules = collect_from_extensions("register_rules")
        for rule in discovered_rules:
            if isinstance(rule, Rule):
                self._rules.append(rule)
        logger.info("ExtensionRegistry: loaded %d rules from extensions", len(discovered_rules))

        discovered_generators = collect_from_extensions("register_generators")
        for gen in discovered_generators:
            if hasattr(gen, "name"):
                self._generators[gen.name] = gen
        logger.info("ExtensionRegistry: loaded %d generators from extensions", len(discovered_generators))

        self._loaded = True
        return self

    # 手动注册
    def register_rule(self, rule: Rule):
        self._rules.append(rule)

    def register_generator(self, generator):
        self._generators[generator.name] = generator

    # 查询
    def get_extension_rules(self) -> List[Rule]:
        return list(self._rules)

    def get_generator(self, name: str):
        return self._generators.get(name)

    def get_all_generators(self) -> Dict[str, object]:
        return dict(self._generators)

    @property
    def is_loaded(self) -> bool:
        return self._loaded


_registry: Optional[ExtensionRegistry] = None


def get_registry() -> ExtensionRegistry:
    """获取全局 ExtensionRegistry 单例。"""
    global _registry
    if _registry is None:
        _registry = ExtensionRegistry()
    return _registry
