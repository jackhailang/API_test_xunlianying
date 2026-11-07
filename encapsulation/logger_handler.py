# -*- coding: utf-8 -*-
"""日志封装。

同时输出到控制台和 output/logs/。格式包含时间、级别、模块、行号和消息。
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from config.setting import LOG_DIR, settings

_LOGGER_NAME = "insurance_api"
_FORMAT = "%(asctime)s | %(levelname)-7s | %(module)s:%(lineno)d | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger() -> logging.Logger:
    """初始化框架日志。重复调用不会叠加 handler。

    入参:
        无。日志级别和文件名来自配置。
    出参:
        名为 insurance_api 的 logger。
    异常:
        OSError: 日志目录或文件无法创建时由底层抛出。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(getattr(logging, settings.log_level))
    logger.propagate = False
    if logger.handlers:
        return logger

    formatter = logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.info(
        "日志已初始化，环境=%s，base_url=%s，日志文件=%s",
        settings.env_key,
        settings.base_url,
        settings.log_file,
    )
    return logger


def get_logger(module_name: str) -> logging.Logger:
    """获取子日志器，日志会汇入统一的文件和控制台 handler。

    入参:
        module_name: 模块名，会出现在子 logger 名称中。
    出参:
        logging.Logger。
    异常:
        无。目录创建失败时由 setup_logger 抛出 OSError。
    """
    setup_logger()
    name = module_name.strip() if module_name else "app"
    return logging.getLogger(f"{_LOGGER_NAME}.{name}")
