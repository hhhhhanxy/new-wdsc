"""
扩展协议 - 文档审查与生成平台

在 extensions/ 目录下放置 Python 模块（.py 文件或包），暴露以下任意函数即可被自动发现：

    register_rules() -> List[Rule]              # 注册审查规则
    register_generators() -> List[BaseGenerator] # 注册生成器

无需修改任何源码，重启应用即生效。
"""
