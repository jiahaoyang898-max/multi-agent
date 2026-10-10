# -*- coding: utf-8 -*-
"""PyCharm 配置修复脚本（智枢套件 / multi-agent）

背景
----
项目原先分两处存放（D:\\data-agent、D:\\knowledge_base），后来合并到
D:\\ruanjian\\multi-agent\\apps\\ 下。但 PyCharm 侧有两处没跟着改：

  1. 根项目 .idea/multi-agent.iml 里缺少 <component name="NewModuleRootManager">，
     模块既没绑定解释器、也没有声明源码根 —— 表现为「所有第三方包 + 所有 app.*
     导入全部报红，但标准库不红」；
  2. 全局 SDK 表 jdk.table.xml 里 'uv (data-agent)' / 'uv (knowledge_base)'
     仍指向项目外的旧副本 —— 解析环境是过期的。

本脚本做两件事
--------------
  A. 重建项目 .idea 下的模块定义（multi-agent.iml / data-agent.iml /
     knowledge-base.iml / modules.xml），幂等，已正确则不动；
  B. 把全局 SDK 表中两个 SDK 的路径改到本项目内的 .venv。

重要
----
PyCharm 运行期间会在退出时用它内存里的配置回写 .idea 与 jdk.table.xml，
把外部改动覆盖掉。因此**建议先完全退出 PyCharm 再运行本脚本**。
检测到 PyCharm 仍在运行时，脚本默认只检查、不写入（可用 --force 强制）。

用法
----
    python fix-pycharm-setup.py            # 推荐：先退出 PyCharm 再执行
    python fix-pycharm-setup.py --dry-run  # 只检查不修改
    python fix-pycharm-setup.py --force    # PyCharm 运行中也强制写入
"""
import argparse
import os
import re
import shutil
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# 目标映射：SDK 名称 -> 本项目中正确的解释器路径
TARGET_SDKS = {
    "uv (data-agent)": os.path.join(
        PROJECT_ROOT, "apps", "data-agent", ".venv", "Scripts", "python.exe"),
    "uv (knowledge_base)": os.path.join(
        PROJECT_ROOT, "apps", "knowledge_base", ".venv", "Scripts", "python.exe"),
}

IDE_NAME = "PyCharm2024.3"

# ---------------------------------------------------------------- .idea 模板
_IDEA_MODULES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<project version="4">
  <component name="ProjectModuleManager">
    <modules>
      <module fileurl="file://$PROJECT_DIR$/.idea/multi-agent.iml" filepath="$PROJECT_DIR$/.idea/multi-agent.iml" />
      <module fileurl="file://$PROJECT_DIR$/.idea/data-agent.iml" filepath="$PROJECT_DIR$/.idea/data-agent.iml" />
      <module fileurl="file://$PROJECT_DIR$/.idea/knowledge-base.iml" filepath="$PROJECT_DIR$/.idea/knowledge-base.iml" />
    </modules>
  </component>
</project>
"""

_IDEA_MULTI_AGENT_IML = """<?xml version="1.0" encoding="UTF-8"?>
<module type="PYTHON_MODULE" version="4">
  <component name="NewModuleRootManager" inherit-compiler-output="true">
    <exclude-output />
    <content url="file://$MODULE_DIR$">
      <excludeFolder url="file://$MODULE_DIR$/node_modules" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent" />
      <excludeFolder url="file://$MODULE_DIR$/apps/knowledge_base" />
    </content>
    <orderEntry type="inheritedJdk" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
  <component name="PyDocumentationSettings">
    <option name="format" value="GOOGLE" />
    <option name="myDocStringFormat" value="Google" />
  </component>
  <component name="TestRunnerService">
    <option name="PROJECT_TEST_RUNNER" value="py.test" />
  </component>
</module>
"""

_IDEA_DATA_AGENT_IML = """<?xml version="1.0" encoding="UTF-8"?>
<module type="PYTHON_MODULE" version="4">
  <component name="NewModuleRootManager" inherit-compiler-output="true">
    <exclude-output />
    <content url="file://$MODULE_DIR$/apps/data-agent">
      <sourceFolder url="file://$MODULE_DIR$/apps/data-agent" isTestSource="false" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/.venv" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/.idea" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/__pycache__" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/logs" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/web/node_modules" />
      <excludeFolder url="file://$MODULE_DIR$/apps/data-agent/web/dist" />
    </content>
    <orderEntry type="jdk" jdkName="uv (data-agent)" jdkType="Python SDK" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
  <component name="PyDocumentationSettings">
    <option name="format" value="GOOGLE" />
    <option name="myDocStringFormat" value="Google" />
  </component>
  <component name="TestRunnerService">
    <option name="PROJECT_TEST_RUNNER" value="py.test" />
  </component>
</module>
"""

_IDEA_KNOWLEDGE_BASE_IML = """<?xml version="1.0" encoding="UTF-8"?>
<module type="PYTHON_MODULE" version="4">
  <component name="NewModuleRootManager" inherit-compiler-output="true">
    <exclude-output />
    <content url="file://$MODULE_DIR$/apps/knowledge_base">
      <sourceFolder url="file://$MODULE_DIR$/apps/knowledge_base" isTestSource="false" />
      <excludeFolder url="file://$MODULE_DIR$/apps/knowledge_base/.venv" />
      <excludeFolder url="file://$MODULE_DIR$/apps/knowledge_base/.idea" />
      <excludeFolder url="file://$MODULE_DIR$/apps/knowledge_base/__pycache__" />
    </content>
    <orderEntry type="jdk" jdkName="uv (knowledge_base)" jdkType="Python SDK" />
    <orderEntry type="sourceFolder" forTests="false" />
  </component>
  <component name="PyDocumentationSettings">
    <option name="format" value="GOOGLE" />
    <option name="myDocStringFormat" value="Google" />
  </component>
  <component name="TestRunnerService">
    <option name="PROJECT_TEST_RUNNER" value="py.test" />
  </component>
</module>
"""

IDEA_FILES = {
    "multi-agent.iml": _IDEA_MULTI_AGENT_IML,
    "data-agent.iml": _IDEA_DATA_AGENT_IML,
    "knowledge-base.iml": _IDEA_KNOWLEDGE_BASE_IML,
    "modules.xml": _IDEA_MODULES_XML,
}


def log(msg):
    print(msg, flush=True)


def pycharm_running():
    """返回正在运行的 pycharm64.exe 进程数。"""
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq pycharm64.exe", "/FO", "CSV"],
            capture_output=True, timeout=30,
        ).stdout
    except Exception:
        return 0
    if not out:
        return 0
    # tasklist 在中文 Windows 下按 GBK 输出，用 replace 兜底避免解码失败
    text = out.decode("gbk", errors="replace") if isinstance(out, bytes) else out
    return sum(1 for line in text.splitlines() if "pycharm64.exe" in line.lower())


def is_module_file_ok(name, content):
    """判断 .idea 文件是否已是期望状态。"""
    if name == "modules.xml":
        if "$PROJECT_DIR$/.idea/multi-agent.iml" not in content:
            return False
        return all(f"$PROJECT_DIR$/.idea/{n}" in content for n in IDEA_FILES if n != "modules.xml")
    if "NewModuleRootManager" not in content:
        return False
    if name == "multi-agent.iml":
        return True  # 容器模块，不强制 sourceFolder
    return "sourceFolder url=" in content


def repair_idea(apply_changes):
    """[A] 重建项目 .idea 模块定义。"""
    log("\n[A] 项目 .idea 模块定义")
    idea_dir = os.path.join(PROJECT_ROOT, ".idea")
    if not os.path.isdir(idea_dir):
        log(f"   [警告] 目录不存在：{idea_dir}")
        return False

    all_good = True
    for name, expected in IDEA_FILES.items():
        path = os.path.join(idea_dir, name)
        if os.path.isfile(path):
            current = open(path, encoding="utf-8", errors="replace").read()
            if is_module_file_ok(name, current):
                log(f"   [OK] {name}（已正确）")
                continue
            if current.strip() == expected.strip():
                log(f"   [OK] {name}（已正确）")
                continue
            status = "已修正" if apply_changes else "需修正"
        else:
            current = None
            status = "已创建" if apply_changes else "缺失"

        all_good = False
        if apply_changes:
            if current is not None:
                backup = f"{path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
                shutil.copy2(path, backup)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(expected)
            log(f"   [{status}] {name}")
        else:
            log(f"   [{status}] {name}")
    return all_good


def find_jdk_table():
    """在常见的 PyCharm 配置目录下定位 jdk.table.xml。"""
    home = os.path.expanduser("~")
    candidates = [
        os.path.join(home, "AppData", "Roaming", "JetBrains", IDE_NAME,
                     "options", "jdk.table.xml"),
        os.path.join(home, "AppData", "Local", "JetBrains", IDE_NAME,
                     "options", "jdk.table.xml"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    base = os.path.join(home, "AppData", "Roaming", "JetBrains")
    if os.path.isdir(base):
        for name in sorted(os.listdir(base)):
            if name.lower().startswith("pycharm"):
                p = os.path.join(base, name, "options", "jdk.table.xml")
                if os.path.isfile(p):
                    return p
    return None


def patch_sdk_path(text, sdk_name, new_path):
    """把指定 SDK 块内的 homePath 换成 new_path。返回 (新文本, 是否改动)。"""
    parts = re.split(r"(?=<jdk\b)", text)
    changed = False
    for i, part in enumerate(parts):
        if f'<name value="{sdk_name}" />' not in part:
            continue
        # 用 lambda 替换，避免 Windows 路径中的反斜杠被当作正则转义序列
        new_part, n = re.subn(r'<homePath value="[^"]*"',
                              lambda _m: f'<homePath value="{new_path}"',
                              part, count=1)
        if n and new_part != part:
            parts[i] = new_part
            changed = True
    return "".join(parts), changed


def repair_global_sdk(apply_changes):
    """[B] 修正全局 SDK 表中的解释器路径。"""
    log("\n[B] 全局 SDK 表 (jdk.table.xml)")

    jdk_path = find_jdk_table()
    if not jdk_path:
        log("   [跳过] 未找到 jdk.table.xml")
        return False
    log(f"   配置文件：{jdk_path}")

    text = open(jdk_path, encoding="utf-8", errors="replace").read()
    original = text
    for sdk_name, new_path in TARGET_SDKS.items():
        if not os.path.isfile(new_path):
            log(f"   [警告] 目标解释器不存在，跳过：{new_path}")
            continue
        text, changed = patch_sdk_path(text, sdk_name, new_path)
        if changed:
            log(f"   [{'已修正' if apply_changes else '需修正'}] {sdk_name}")
            log(f"          -> {new_path}")
        elif f'<name value="{sdk_name}" />' in text:
            log(f"   [OK] {sdk_name}（已指向 {new_path}）")
        else:
            log(f"   [未找到] SDK 表中没有 {sdk_name}")

    if text == original:
        return True
    if not apply_changes:
        return False

    backup = f"{jdk_path}.bak-{time.strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(jdk_path, backup)
    log(f"   已备份：{backup}")
    with open(jdk_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    log("   写入完成")
    return True


def main():
    ap = argparse.ArgumentParser(description="PyCharm 配置修复（智枢套件 / multi-agent）")
    ap.add_argument("--dry-run", action="store_true", help="只检查不修改")
    ap.add_argument("--force", action="store_true",
                    help="检测到 PyCharm 运行时也强制写入（不推荐，可能被覆盖）")
    args = ap.parse_args()

    log("=" * 74)
    log("PyCharm 配置修复  ——  智枢套件 / multi-agent")
    log("=" * 74)
    log(f"项目根目录：{PROJECT_ROOT}")

    running = pycharm_running()
    if args.dry_run:
        apply_changes = False
        log("\n模式：试运行（只检查）")
    elif running and not args.force:
        apply_changes = False
        log(f"\n[注意] 检测到 PyCharm 正在运行（{running} 个进程）")
        log("       PyCharm 退出时会回写配置，覆盖本次改动。")
        log("       本次仅做检查。请完全退出 PyCharm 后重新运行本脚本。")
    else:
        apply_changes = True
        log("\n模式：写入")

    repair_idea(apply_changes)
    repair_global_sdk(apply_changes)

    log("\n" + "=" * 74)
    if apply_changes:
        log("完成。请在 PyCharm 中打开项目，确认：")
        log("  · Settings → Project → Python Interpreter 指向项目内 .venv")
        log("  · 项目树中 apps/data-agent、apps/knowledge_base 均无导入报红")
        log("  · 运行下拉框可用：① 问数后端(8000) ② 嵌入(8002) ③ 查询(8001) ④ 导入(8004)")
    else:
        log("请按顺序操作：")
        log("  1. 完全退出 PyCharm（任务管理器里确认没有 pycharm64.exe）")
        log(f"  2. 运行：python {os.path.basename(__file__)}")
        log("  3. 重新打开 PyCharm")
    log("=" * 74)


if __name__ == "__main__":
    main()
