"""
扩展自动发现引擎。

扫描 extensions/ 目录，加载含有 hook 函数的 Python 模块。
"""
import importlib
import importlib.util
import logging
from pathlib import Path
from typing import List, Any

logger = logging.getLogger(__name__)

EXTENSIONS_DIR = Path(__file__).parent

EXTENSION_HOOKS = (
    "register_rules",
    "register_generators",
    "register_security_checks",
    "register_templates",
)


def _is_extension_module(path: Path) -> bool:
    if path.is_file() and path.suffix == ".py" and not path.name.startswith("_"):
        return True
    if path.is_dir() and (path / "__init__.py").exists() and not path.name.startswith("_"):
        return True
    return False


def discover_extensions() -> List[Any]:
    """扫描 extensions/ 目录，返回所有含有 hook 函数的模块列表。"""
    modules = []

    if not EXTENSIONS_DIR.exists():
        return modules

    for entry in sorted(EXTENSIONS_DIR.iterdir()):
        if entry.name.startswith(("_", ".")):
            continue
        if not _is_extension_module(entry):
            continue

        module_name = f"extensions.{entry.stem}"

        try:
            if entry.is_dir():
                module = importlib.import_module(module_name)
            else:
                spec = importlib.util.spec_from_file_location(module_name, str(entry))
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

            has_hook = any(hasattr(module, h) for h in EXTENSION_HOOKS)
            if has_hook:
                modules.append(module)
                logger.info("Loaded extension: %s", module_name)
            else:
                logger.debug("Skipped %s: no extension hooks", module_name)

        except Exception as e:
            logger.error("Failed to load extension %s: %s", module_name, e)

    return modules


def collect_from_extensions(hook_name: str) -> List:
    """调用所有扩展模块的指定 hook 函数，收集返回结果。"""
    results = []
    for module in discover_extensions():
        hook = getattr(module, hook_name, None)
        if hook and callable(hook):
            try:
                items = hook()
                if isinstance(items, (list, tuple)):
                    results.extend(items)
            except Exception as e:
                logger.error("Extension %s.%s() failed: %s", module.__name__, hook_name, e)
    return results
