# -*- coding: utf-8 -*-
"""保险出单全流程。

执行顺序固定为：读取 Excel -> 判断 enabled -> 初始化上下文 ->
试算替换/请求/提取/断言 -> 核保替换/请求/提取/断言 -> 承保替换/请求/提取/断言。
响应字段路径只出现在 YAML 的 extract 中。
"""
from __future__ import annotations

import json
from typing import Any, Dict

import allure
import pytest

from common.assert_util import execute_assertions
from common.context import Context
from common.excel_util import is_case_enabled, read_excel_cases
from common.exception_util import ConfigError, ExtractError, RequestError
from common.extract_util import apply_extract
from common.replace_util import replace_data
from common.yaml_util import load_yaml, resolve_testdata_file
from encapsulation.http_client import HttpClient
from encapsulation.logger_handler import get_logger

logger = get_logger("insurance_flow")


def _dump(data: Any) -> str:
    """把报文转成 Allure 可展示的 JSON 文本。

    入参:
        data: 请求体、响应体或上下文字典。
    出参:
        带缩进的 JSON 字符串。
    异常:
        无。无法序列化的对象会转成字符串。
    """
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def _attach_json(name: str, data: Any) -> None:
    """向当前 Allure 步骤附加 JSON。

    入参:
        name: 附件名称。
        data: 要展示的数据。
    出参:
        无。
    异常:
        无。
    """
    allure.attach(_dump(data), name=name, attachment_type=allure.attachment_type.JSON)


def _attach_text(name: str, content: str) -> None:
    """向当前 Allure 步骤附加文本。

    入参:
        name: 附件名称。
        content: 文本内容。
    出参:
        无。
    异常:
        无。
    """
    allure.attach(content or "", name=name, attachment_type=allure.attachment_type.TEXT)


def _require_api_fields(api_def: Dict[str, Any], yaml_path: str) -> None:
    """检查接口 YAML 的必填项。

    入参:
        api_def: YAML 内容。
        yaml_path: 文件路径，用于异常提示。
    出参:
        无。
    异常:
        ConfigError: 缺少 name、method 或 url。
    """
    missing = [field for field in ("name", "method", "url") if not str(api_def.get(field) or "").strip()]
    if missing:
        raise ConfigError(f"YAML 缺少必填项 {missing}：{yaml_path}")


def execute_api_step(step_name: str, yaml_relative: str, context: Context, client: HttpClient) -> None:
    """执行一个接口步骤：替换、请求、提取、断言。

    入参:
        step_name: 步骤名称，例如试算、核保、承保。
        yaml_relative: Excel 中的 YAML 相对路径。
        context: 当前用例上下文。提取结果会写回这里。
        client: HTTP 客户端。
    出参:
        无。关联变量通过 context 传递给下一步。
    异常:
        ConfigError: YAML 结构不合法或文件不存在。
        VariableNotFoundError: 报文引用了还不存在的变量。
        RequestError: 请求超时或连接失败。
        ExtractError: extract 路径在响应中不存在。
        AssertionError: YAML 断言失败。pytest 会据此把用例标为失败。
    """
    yaml_path = resolve_testdata_file(yaml_relative)
    api_def = load_yaml(yaml_path)
    _require_api_fields(api_def, str(yaml_path))
    step_title = f"{step_name}：{api_def['name']}"

    with allure.step(step_title):
        _attach_text("YAML路径", str(yaml_path))
        logger.info("开始步骤 %s | 文件=%s", step_title, yaml_path)

        variables = context.as_dict()
        method = str(api_def["method"]).strip().upper()
        url = replace_data(api_def["url"], variables)
        headers = replace_data(api_def.get("headers") or {}, variables)
        params = replace_data(api_def.get("params") or {}, variables)
        body = replace_data(api_def.get("json"), variables) if "json" in api_def else None
        timeout = api_def.get("timeout")

        _attach_text("请求方法", method)
        _attach_text("请求地址", str(url))
        _attach_json("请求头", headers)
        _attach_json("请求报文", body)

        try:
            result = client.request(
                method=method,
                url=str(url),
                headers=headers,
                json_body=body,
                params=params,
                timeout=timeout,
            )
        except RequestError as exc:
            _attach_text("请求异常", str(exc))
            logger.exception("步骤 %s 请求失败", step_title)
            raise

        _attach_text("响应状态码", str(result.status_code))
        _attach_text("响应耗时毫秒", f"{result.elapsed_ms:.2f}")
        if result.json_data is not None:
            _attach_json("响应报文", result.json_data)
        else:
            _attach_text("响应报文", result.text)

        try:
            extracted = apply_extract(result.json_data, api_def.get("extract") or {}, context)
        except ExtractError as exc:
            _attach_text("变量提取失败", str(exc))
            logger.exception("步骤 %s 提取变量失败", step_title)
            raise

        _attach_json("本次提取变量", extracted)
        _attach_json("当前上下文变量名", context.keys())
        logger.info("步骤 %s 提取变量：%s", step_title, _dump(extracted))

        try:
            messages = execute_assertions(
                rules=api_def.get("assert") or [],
                status_code=result.status_code,
                response_text=result.text,
                response_json=result.json_data,
                variables=context.as_dict(),
            )
        except AssertionError as exc:
            _attach_text("断言结果", str(exc))
            logger.error("步骤 %s 断言失败：%s", step_title, exc)
            raise

        _attach_text("断言结果", "\n".join(messages))
        logger.info("步骤 %s 完成 | %s", step_title, "；".join(messages))


def _case_id(case: Dict[str, str]) -> str:
    """生成 pytest 参数化用例编号。

    入参:
        case: Excel 中的一行用例。
    出参:
        用例编号。
    异常:
        无。
    """
    return str(case.get("case_id") or "CASE")


@allure.feature("保险出单")
@allure.story("试算核保承保全流程")
@pytest.mark.insurance
@pytest.mark.parametrize("case", read_excel_cases(), ids=_case_id)
def test_insurance_full_flow(case: Dict[str, str], api_client: HttpClient) -> None:
    """按 Excel 一行数据串联试算、核保和承保。

    入参:
        case: Excel 用例，包含三个 YAML 路径和 enabled。
        api_client: pytest 夹具提供的 HTTP 客户端。
    出参:
        无。
    异常:
        AssertionError: 任一接口断言失败。
        VariableNotFoundError: 后续报文缺少前置 extract 变量，例如 orderId。
        ExtractError: YAML 配置的响应路径和真实返回不一致。
        RequestError: 网络或超时失败。
    """
    allure.dynamic.title(f"{case['case_id']} {case['case_name']}")
    allure.dynamic.description(case.get("description") or case["case_name"])
    allure.dynamic.parameter("case_id", case["case_id"])
    allure.dynamic.severity(allure.severity_level.CRITICAL)

    if not is_case_enabled(case.get("enabled")):
        pytest.skip(f"用例 {case['case_id']} 的 enabled={case.get('enabled')}，已跳过")

    logger.info("开始用例 %s | %s", case["case_id"], case["case_name"])
    context = Context()
    context.init_builtins()
    _attach_json("初始内置变量", {key: context.get(key) for key in context.keys()})

    # 步骤顺序和 Excel 列绑定。订单号、保费都由对应 YAML 的 extract 写入 context。
    steps = [
        ("试算", case["calculate_yaml"]),
        ("核保", case["validate_yaml"]),
        ("承保", case["accept_yaml"]),
    ]
    for step_name, yaml_relative in steps:
        execute_api_step(step_name, yaml_relative, context, api_client)

    logger.info("用例 %s 执行完成，上下文变量：%s", case["case_id"], context.keys())
