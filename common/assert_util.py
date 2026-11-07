# -*- coding: utf-8 -*-
"""断言工具。

断言类型和期望值都来自 YAML。比较前会先替换期望值中的 ${变量名}。
失败时抛出 AssertionError，pytest 会把对应用例标记为失败。
"""
from __future__ import annotations

from typing import Any, Dict, List

from common.exception_util import ConfigError, ExtractError
from common.extract_util import get_by_path
from common.replace_util import replace_data


def _values_equal(actual: Any, expected: Any) -> bool:
    """比较两个值。类型不同但文本相同也视为相等，避免 624 和 \"624\" 误报。

    入参:
        actual: 实际值。
        expected: 期望值。
    出参:
        相等返回 True。
    异常:
        无。
    """
    if actual == expected:
        return True
    return str(actual) == str(expected)


def _check_rule(rule: Dict[str, Any], status_code: int, response_text: str, response_json: Any) -> str:
    """执行一条断言。

    入参:
        rule: 单条断言配置，至少包含 type。
        status_code: HTTP 状态码。
        response_text: 响应原文。
        response_json: 解析后的 JSON，解析失败时为 None。
    出参:
        本条断言通过的说明。
    异常:
        ConfigError: 断言配置缺少字段或类型不支持。
        AssertionError: 实际结果和期望不一致。
    """
    if not isinstance(rule, dict):
        raise ConfigError(f"断言规则必须是字典，当前值：{rule}")

    rule_type = str(rule.get("type") or "").strip().lower()
    supported = {"status_code", "equals", "contains", "not_empty"}
    if rule_type not in supported:
        raise ConfigError(f"不支持的断言类型 {rule_type or '(空)'}。可选：status_code、equals、contains、not_empty")

    if rule_type == "status_code":
        if "expected" not in rule:
            raise ConfigError("status_code 断言缺少 expected")
        expected = int(rule["expected"])
        if status_code != expected:
            raise AssertionError(f"断言失败：期望 status_code={expected}，实际 status_code={status_code}")
        return f"status_code 通过，实际值 {status_code}"

    path = str(rule.get("path") or "").strip()
    if rule_type in {"equals", "not_empty", "contains"} and rule_type != "contains":
        if not path:
            raise ConfigError(f"{rule_type} 断言缺少 path")

    if rule_type == "contains" and not path:
        expected = rule.get("expected")
        if expected is None:
            raise ConfigError("contains 断言缺少 expected")
        if str(expected) not in response_text:
            raise AssertionError(
                f"断言失败：响应文本不包含 {expected!r}。响应片段：{response_text[:1500]}"
            )
        return f"响应文本包含 {expected!r}"

    if response_json is None:
        raise AssertionError(f"断言失败：响应不是 JSON，无法按路径 {path} 断言。响应片段：{response_text[:1500]}")

    try:
        actual = get_by_path(response_json, path)
    except ExtractError as exc:
        raise AssertionError(f"断言失败：{exc}") from exc

    if rule_type == "not_empty":
        if actual is None or actual == "" or actual == [] or actual == {}:
            raise AssertionError(f"断言失败：路径 {path} 期望非空，实际值是 {actual!r}")
        return f"路径 {path} 非空，实际值 {actual!r}"

    if "expected" not in rule:
        raise ConfigError(f"{rule_type} 断言缺少 expected")
    expected = rule["expected"]

    if rule_type == "equals":
        if not _values_equal(actual, expected):
            raise AssertionError(
                f"断言失败：路径 {path} 期望 {expected!r}，实际 {actual!r}"
            )
        return f"路径 {path} 等于 {expected!r}"

    if rule_type == "contains":
        if str(expected) not in str(actual):
            raise AssertionError(
                f"断言失败：路径 {path} 期望包含 {expected!r}，实际 {actual!r}"
            )
        return f"路径 {path} 包含 {expected!r}"

    raise ConfigError(f"断言类型 {rule_type} 未实现")


def execute_assertions(
    rules: List[Dict[str, Any]],
    status_code: int,
    response_text: str,
    response_json: Any,
    variables: Dict[str, Any],
) -> List[str]:
    """按顺序执行全部断言。

    入参:
        rules: YAML 中的 assert 列表。
        status_code: HTTP 状态码。
        response_text: 响应原文。
        response_json: 响应 JSON；不是 JSON 时传 None。
        variables: 上下文变量，用于替换期望值里的占位符。
    出参:
        每条断言的通过说明。
    异常:
        ConfigError: 断言配置不合法。
        AssertionError: 任意一条断言失败。失败前的说明不会继续执行后续断言。
        VariableNotFoundError: 期望值引用了不存在的变量。
    """
    if not rules:
        return ["未配置 assert，本次只完成请求和变量提取"]
    if not isinstance(rules, list):
        raise ConfigError("YAML 的 assert 必须是列表")

    rendered_rules = replace_data(rules, variables)
    messages = []
    for index, rule in enumerate(rendered_rules, start=1):
        message = _check_rule(rule, status_code, response_text, response_json)
        messages.append(f"第 {index} 条：{message}")
    return messages
