"""纯客户端进程的内存守卫：阻止 transformers / torch 被拖进进程。

背景
----
知库的查询服务(8101)与导入服务(8104)是**纯客户端**：向量化走 8102 嵌入服务，
重排走 DashScope HTTP，本进程不需要任何本地模型。但是：

    langgraph → langchain_core.language_models.base
        → `from transformers import GPT2TokenizerFast`
        → transformers 导入 torch
        → torch 映射 cudnn / cublas / cudart / torch_cuda 整套 CUDA DLL

实测每个进程因此多出 1.5~2GB **提交量**（这台机器是纯 CPU，这些 CUDA 库一次都
用不上），三个知库进程合计约 12GB 提交量，把宿主提交上限吃光，才出现
`WinError 1455` / `DefaultCPUAllocator: not enough memory`。

原理
----
langchain_core 那行导入是被 `try/except ImportError` 包着的，失败只影响一个从未
被调用的 GPT-2 分词器（`_HAS_TRANSFORMERS=False` 的降级路径）。所以只要让
`import transformers` 直接失败即可，torch 与整套 CUDA 栈都不会再被加载。

用法
----
在入口文件最顶部、任何 langchain / processor 导入之前调用：

    from tool.no_torch_guard import disable_local_torch
    disable_local_torch()

开关
----
- `KB_NO_LOCAL_TORCH=0`：关闭本优化（纯排查用）。
- 未配置 `EMBEDDING_SERVICE_URL` 时不生效——那种情况下本地模型是主路径，
  拦住 transformers 会让嵌入功能不可用。
"""

import os
import sys


def disable_local_torch() -> bool:
    """按需屏蔽 transformers 的导入，返回是否生效。

    置 `sys.modules[name] = None` 会让后续的 `import x` / `from x import y`
    直接抛 ImportError，且不会真正执行任何模块代码。
    """
    if os.getenv("KB_NO_LOCAL_TORCH", "1").strip() == "0":
        return False

    # 入口文件通常早于各 config 模块，这里先把 .env 读进来再判断
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # dotenv 缺失不影响主流程
        pass

    if not (os.getenv("EMBEDDING_SERVICE_URL") or "").strip():
        return False  # 没有远程嵌入服务，本地模型是主路径，不能拦

    # 幂等：重复调用无副作用（注意不要用 `sys.modules.get(...) is None` 判断"已拦截"，
    # 键不存在时它同样返回 None，会导致本次 assignment 被跳过）
    sys.modules["transformers"] = None
    return True
