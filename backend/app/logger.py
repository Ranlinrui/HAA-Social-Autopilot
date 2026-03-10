"""
统一日志模块
- 同时输出到控制台和内存缓冲（供前端 /api/logs 查询）
- 内存最多保留 500 条，超出自动丢弃最旧的
"""
import logging
import sys
from collections import deque
from datetime import datetime
from typing import Deque

# 内存日志缓冲，最多 500 条
_log_buffer: Deque[dict] = deque(maxlen=500)


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord):
        _log_buffer.append({
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "level": record.levelname,
            "module": record.name,
            "message": self.format(record),
        })


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 控制台输出
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    ))

    # 内存缓冲
    buf = BufferHandler()
    buf.setLevel(logging.DEBUG)
    buf.setFormatter(logging.Formatter("%(message)s"))

    logger.addHandler(console)
    logger.addHandler(buf)
    return logger


def get_logs(level: str = None, module: str = None, limit: int = 100) -> list:
    logs = list(_log_buffer)
    if level:
        logs = [l for l in logs if l["level"] == level.upper()]
    if module:
        logs = [l for l in logs if module in l["module"]]
    return list(reversed(logs))[-limit:]
