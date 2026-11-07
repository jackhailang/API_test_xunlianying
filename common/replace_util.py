# -*- coding: utf-8 -*-
"""占位符替换。

递归处理 dict、list、str。整段文本恰好是 ${变量名} 时保留原类型；
嵌在其他文字中时转成字符串，例如 hebaojiaoyanma_${timestamp}。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict

from common.exception_util import VariableNotFoundError

# 匹配 ${变量名}。变量名本身不允许再包含花括号。
_PATTERN = re.compile(r"\$\{([^{}]+)\}")

_MISSING_HINTS = {
    "orderId": "请检查核保 YAML 的 extract 配置",
    "totalPremium": "请检查试算 YAML 的 extract 配置",
    "outChannelOrderId": "请检查试算 YAML 的 extract 配置，或确认内置变量已初始化",
}


def _missing_message(name: str) -> str:
    """组装变量缺失提示。

    入参:
        name: 缺失的变量名。
    出参:
        中文异常文案。
    异常:
        无。
    """
    hint = _MISSING_HINTS.get(
        name,
        "请检查前置接口 YAML 的 extract 配置，或确认它是否为内置变量"
        "（today、now_time、timestamp、uuid、outChannelOrderId、bkSerial、orderNo）",
    )
    return f"上下文变量 {name} 不存在，{hint}"


def _require(name: str, variables: Dict[str, Any]) -> Any:
    """读取变量，不存在时抛出明确异常。

    入参:
        name: 变量名。
        variables: 当前上下文变量。
    出参:
        变量值。
    异常:
        VariableNotFoundError: 变量不存在。
    """
    key = name.strip()
    if key not in variables:
        raise VariableNotFoundError(_missing_message(key))
    return variables[key]


def _replace_string(text: str, variables: Dict[str, Any]) -> Any:
    """替换一个字符串里的全部占位符。

    入参:
        text: 原始字符串。
        variables: 上下文变量。
    出参:
        替换后的值。整段占位符返回原始类型，其余情况返回字符串。
    异常:
        VariableNotFoundError: 任一占位符没有对应变量。
    """
    matches = list(_PATTERN.finditer(text))
    if not matches:
        return text

    if len(matches) == 1 and matches[0].group(0) == text.strip() and text.strip() == text:
        return _require(matches[0].group(1), variables)

    def _to_text(match: re.Match) -> str:
        value = _require(match.group(1), variables)
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    return _PATTERN.sub(_to_text, text)


def replace_data(data: Any, variables: Dict[str, Any]) -> Any:
    """递归替换请求数据中的 ${变量名}。

    入参:
        data: YAML 中的 url、headers、json、params 或断言期望值。
        variables: 上下文字典。
    出参:
        新的数据结构，不修改入参。
    异常:
        VariableNotFoundError: 占位符引用的变量不存在。
    """
    if isinstance(data, dict):
        return {key: replace_data(value, variables) for key, value in data.items()}
    if isinstance(data, list):
        return [replace_data(item, variables) for item in data]
    if isinstance(data, str):
        return _replace_string(data, variables)
    return data
