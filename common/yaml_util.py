# -*- coding: utf-8 -*-
"""YAML 文件读取。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

from common.exception_util import ConfigError
from config.setting import BASE_DIR, TESTDATA_DIR


def load_yaml(path: Path) -> Dict[str, Any]:
    """读取 YAML 文件。

    入参:
        path: 文件路径。
    出参:
        根节点字典。空文件返回空字典。
    异常:
        ConfigError: 文件不存在、格式错误或根节点不是字典。
    """
    if not path.exists():
        raise ConfigError(f"YAML 文件不存在：{path}")
    try:
        with path.open("r", encoding="utf-8") as file:
            data = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        raise ConfigError(f"YAML 格式错误：{path}，原因：{exc}") from exc
    except OSError as exc:
        raise ConfigError(f"YAML 读取失败：{path}，原因：{exc}") from exc

    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(f"YAML 根节点必须是字典：{path}")
    return data


def resolve_testdata_file(relative_path: str) -> Path:
    """把 Excel 中的相对路径解析成测试数据文件。

    入参:
        relative_path: 例如 Transaction/calculate.yaml，也支持 testdata/Transaction/calculate.yaml。
    出参:
        存在的绝对路径。
    异常:
        ConfigError: 路径为空或文件不存在。
    """
    text = "" if relative_path is None else str(relative_path).strip()
    if not text:
        raise ConfigError("YAML 路径不能为空，请检查 Excel 对应用例列")

    path = Path(text)
    if path.is_absolute():
        candidate = path
    else:
        normalized = text.replace("\\", "/")
        if normalized.startswith("testdata/"):
            candidate = BASE_DIR / text
        else:
            candidate = TESTDATA_DIR / text

    if not candidate.exists():
        raise ConfigError(f"YAML 文件不存在：{candidate}。请检查 Excel 中的路径是否相对 testdata 目录")
    return candidate
