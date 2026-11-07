# -*- coding: utf-8 -*-
"""全局配置读取。

业务代码只依赖本模块，不直接散落读取 IP、超时和数据库口令。
敏感信息优先来自环境变量：TEST_ENV、DB_HOST、DB_PORT、DB_USER、DB_PASSWORD、DB_NAME。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

from common.exception_util import ConfigError

# 项目根目录：insurance_api_auto
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "config.yaml"
TESTDATA_DIR = BASE_DIR / "testdata"
CASE_EXCEL_PATH = TESTDATA_DIR / "insurance_cases.xlsx"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = OUTPUT_DIR / "logs"
REPORT_DIR = OUTPUT_DIR / "reports"
RESULT_DIR = OUTPUT_DIR / "results"

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def _read_config_file(path: Path) -> Dict[str, Any]:
    """读取配置 YAML。

    入参:
        path: 配置文件路径。
    出参:
        配置字典。
    异常:
        ConfigError: 文件不存在、内容为空或根节点不是字典。
    """
    if not path.exists():
        raise ConfigError(f"配置文件不存在：{path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError(f"配置文件 YAML 格式错误：{path}，原因：{exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"配置文件根节点必须是字典：{path}")
    return data


def _as_int(value: Any, field_name: str) -> int:
    """把配置值转成整数。

    入参:
        value: 原始配置值。
        field_name: 字段名，用于异常提示。
    出参:
        整数值。
    异常:
        ConfigError: 值无法转换为整数。
    """
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"配置项 {field_name} 必须是整数，当前值：{value}") from exc


class Settings:
    """运行期配置对象。导入时加载一次，测试会话内重复使用。"""

    def __init__(self) -> None:
        self.env_key = "test"
        self.env_name = "测试环境"
        self.base_url = ""
        self.timeout = 30
        self.log_level = "INFO"
        self.log_file = LOG_DIR / "insurance_api.log"
        self.database: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """重新加载配置文件和环境变量。

        入参:
            无。
        出参:
            无。结果写入当前对象属性。
        异常:
            ConfigError: 环境名不存在、超时或日志级别不合法。
        """
        raw = _read_config_file(CONFIG_PATH)
        environments = raw.get("environments") or {}
        if not isinstance(environments, dict) or not environments:
            raise ConfigError("config.yaml 中 environments 不能为空")

        env_key = os.getenv("TEST_ENV") or str(raw.get("current_env") or "test")
        env_key = env_key.strip()
        if env_key not in environments:
            available = "、".join(environments.keys())
            raise ConfigError(f"环境 {env_key} 未定义，可选环境：{available}")

        current = environments[env_key] or {}
        base_url = str(current.get("base_url") or "").strip()
        if not base_url:
            raise ConfigError(f"环境 {env_key} 未配置 base_url")

        log_cfg = raw.get("log") or {}
        log_level = str(log_cfg.get("level") or "INFO").strip().upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigError(f"日志级别不合法：{log_level}，可选：{', '.join(sorted(_LOG_LEVELS))}")

        file_name = str(log_cfg.get("file_name") or "insurance_api.log").strip()
        db_cfg = raw.get("database") or {}
        if not isinstance(db_cfg, dict):
            raise ConfigError("database 配置必须是字典")

        self.env_key = env_key
        self.env_name = str(current.get("name") or env_key)
        self.base_url = base_url.rstrip("/")
        self.timeout = _as_int(raw.get("timeout", 30), "timeout")
        self.log_level = log_level
        self.log_file = LOG_DIR / file_name
        self.database = {
            "host": os.getenv("DB_HOST") or str(db_cfg.get("host") or ""),
            "port": _as_int(os.getenv("DB_PORT") or db_cfg.get("port", 3306), "database.port"),
            "user": os.getenv("DB_USER") or str(db_cfg.get("user") or ""),
            "password": os.getenv("DB_PASSWORD", str(db_cfg.get("password") or "")),
            "database": os.getenv("DB_NAME") or str(db_cfg.get("database") or ""),
            "charset": str(db_cfg.get("charset") or "utf8mb4"),
        }


# 全局单例。测试代码通过 settings.base_url、settings.timeout 读取。
settings = Settings()
