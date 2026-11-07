# -*- coding: utf-8 -*-
"""响应变量提取。

路径全部来自 YAML 的 extract，例如 data.orderId、data.insurants.0.coverages.0.actualPrem。
本模块不包含任何保险业务字段的默认路径。
"""
from __future__ import annotations

import json
from typing import Any, Dict

from common.context import Context
from common.exception_util import ConfigError, ExtractError


def _snippet(payload: Any, limit: int = 1500) -> str:
    """把响应压缩成日志片段。

    入参:
        payload: 响应 JSON 或原始文本。
        limit: 最大字符数。
    出参:
        截断后的文本。
    异常:
        无。无法序列化时退回 repr。
    """
    try:
        if isinstance(payload, str):
            text = payload
        else:
            text = json.dumps(payload, ensure_ascii=False)
    except TypeError:
        text = repr(payload)
    if len(text) <= limit:
        return text
    return text[:limit] + "...(已截断)"


def get_by_path(data: Any, path: str) -> Any:
    """按点路径从 JSON 中取值。

    入参:
        data: 响应 JSON，可以是 dict 或 list。
        path: 点路径。列表下标写成数字，例如 data.items.0.id。
    出参:
        路径对应的原始值。
    异常:
        ExtractError: 路径为空、中间节点类型不符或字段不存在。
    """
    raw_path = "" if path is None else str(path).strip()
    if not raw_path:
        raise ExtractError("提取路径不能为空，请检查 YAML 的 extract 配置")

    current = data
    walked = []
    for segment in raw_path.split("."):
        walked.append(segment)
        location = ".".join(walked)
        if isinstance(current, dict):
            if segment not in current:
                raise ExtractError(
                    f"响应中不存在路径 {raw_path}，已走到 {location} 时找不到字段 {segment}。"
                    f"请根据真实接口响应修改 YAML 的 extract，不要在 Python 中硬编码该字段。"
                    f"响应片段：{_snippet(data)}"
                )
            current = current[segment]
            continue
        if isinstance(current, list):
            if not segment.isdigit():
                raise ExtractError(
                    f"路径 {location} 当前节点是数组，下标必须是数字，实际写成了 {segment}。"
                    f"响应片段：{_snippet(data)}"
                )
            index = int(segment)
            if index >= len(current):
                raise ExtractError(
                    f"路径 {location} 下标越界，数组长度是 {len(current)}。"
                    f"响应片段：{_snippet(data)}"
                )
            current = current[index]
            continue
        raise ExtractError(
            f"路径 {location} 无法继续取值，当前节点类型是 {type(current).__name__}。"
            f"请检查 YAML extract 路径。响应片段：{_snippet(data)}"
        )
    return current


def extract_variables(response_json: Any, rules: Dict[str, Any]) -> Dict[str, Any]:
    """按 extract 规则提取变量，不负责写入上下文。

    入参:
        response_json: 响应 JSON。
        rules: YAML extract 字典，键是变量名，值是点路径。
    出参:
        提取出的变量字典。
    异常:
        ConfigError: extract 不是字典，或某条规则没有路径。
        ExtractError: 响应不是 JSON，或路径不存在。
    """
    if not rules:
        return {}
    if not isinstance(rules, dict):
        raise ConfigError("YAML 的 extract 必须是字典，格式为 变量名: 点路径")
    if not isinstance(response_json, (dict, list)):
        raise ExtractError(
            "响应不是 JSON 对象或数组，无法按 extract 提取变量。"
            f"请先确认接口是否返回 JSON。响应片段：{_snippet(response_json)}"
        )

    extracted: Dict[str, Any] = {}
    for name, path in rules.items():
        variable_name = str(name).strip()
        if not variable_name:
            raise ConfigError("extract 中存在空的变量名")
        if path is None or str(path).strip() == "":
            raise ConfigError(f"变量 {variable_name} 未配置提取路径")
        extracted[variable_name] = get_by_path(response_json, str(path).strip())
    return extracted


def apply_extract(response_json: Any, rules: Dict[str, Any], context: Context) -> Dict[str, Any]:
    """提取变量并写入上下文。同名变量会覆盖旧值。

    入参:
        response_json: 响应 JSON。
        rules: YAML extract 配置。
        context: 当前用例上下文。
    出参:
        本次新写入的变量。
    异常:
        ConfigError: extract 配置不合法。
        ExtractError: 路径在响应中不存在。
    """
    extracted = extract_variables(response_json, rules)
    context.update(extracted)
    return extracted
