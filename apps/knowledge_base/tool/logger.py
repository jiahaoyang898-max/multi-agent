import sys
import logging
import colorlog

# Windows 中文环境下，stdout/stderr 一旦被重定向到管道/文件，CPython 会退回系统
# ANSI 代码页（cp936/GBK）编码；下游按 UTF-8 读取时中文就会变成乱码。
# 这里在创建任何 handler 之前统一把标准流切到 UTF-8，保证日志始终是 UTF-8 字节。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# 初始化全局日志对象
logger = logging.getLogger()
# 设置日志的默认的级别
logger.setLevel(logging.INFO)

# 加载彩色日志处理器
handler = colorlog.StreamHandler()
# 定义日志输出的格式
handler.setFormatter(colorlog.ColoredFormatter(
    '%(log_color)s%(asctime)s - %(filename)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',  # INFO 显示为绿色
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'bold_red',
    }
))

# logger.handlers.clear()

# 应用日志配置信息
logger.addHandler(handler)