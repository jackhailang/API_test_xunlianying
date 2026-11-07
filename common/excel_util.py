# -*- coding: utf-8 -*-
"""Excel 用例读取。

每行用例描述一条保险出单流程，具体报文放在三个 YAML 文件中，Excel 只保存索引。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from openpyxl import load_workbook

from common.exception_util import ConfigError
from config.setting import CASE_EXCEL_PATH
from encapsulation.logger_handler import get_logger

logger = get_logger("excel_util")

# Excel 表头固定，新增列时同步修改 create_excel.py。
EXCEL_HEADERS = [
    "case_id",
    "case_name",
    "calculate_yaml",
    "validate_yaml",
    "accept_yaml",
    "enabled",
    "description",
]

_ENABLED_VALUES = {"Y", "YES", "TRUE", "1", "是", "启用"}


def is_case_enabled(value: Any) -> bool:
    """判断一行用例是否执行。

    入参:
        value: Excel 的 enabled 单元格。
    出参:
        Y/YES/TRUE/1/是/启用 返回 True，其余返回 False。
    异常:
        无。
    """
    text = "" if value is None else str(value).strip()
    return text.upper() in _ENABLED_VALUES or text in _ENABLED_VALUES


def _cell_text(value: Any) -> str:
    """把单元格转成去掉首尾空白的字符串。

    入参:
        value: openpyxl 读到的原始值。
    出参:
        字符串。空单元格返回空字符串。
    异常:
        无。
    """
    if value is None:
        return ""
    return str(value).strip()


def read_excel_cases(excel_path: Path | None = None) -> List[Dict[str, str]]:
    """读取全部用例行。pytest 参数化在收集阶段调用本函数。

    入参:
        excel_path: Excel 路径。为空时使用 config.setting 中的默认文件。
    出参:
        用例字典列表。enabled 保留原始文本，是否跳过由测试函数判断。
    异常:
        ConfigError: 文件不存在、没有表头或缺少必填列。
    """
    path = Path(excel_path) if excel_path else CASE_EXCEL_PATH
    if not path.exists():
        raise ConfigError(
            f"用例 Excel 不存在：{path}。请先在项目根目录执行：python testdata/create_excel.py"
        )

    try:
        workbook = load_workbook(path, data_only=True)
    except OSError as exc:
        raise ConfigError(f"Excel 读取失败：{path}，原因：{exc}") from exc

    sheet = workbook.active
    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise ConfigError(f"Excel 没有内容：{path}")

    headers = [_cell_text(item) for item in rows[0]]
    header_index = {name: index for index, name in enumerate(headers) if name}
    missing = [name for name in EXCEL_HEADERS if name not in header_index]
    if missing:
        raise ConfigError(f"Excel 缺少列 {missing}，当前表头：{headers}")

    cases: List[Dict[str, str]] = []
    for offset, row in enumerate(rows[1:], start=2):
        if row is None or all(item is None or str(item).strip() == "" for item in row):
            continue

        record = {
            name: _cell_text(row[header_index[name]]) if header_index[name] < len(row) else ""
            for name in EXCEL_HEADERS
        }
        if not record["case_id"]:
            raise ConfigError(f"Excel 第 {offset} 行 case_id 不能为空")
        if not record["enabled"]:
            logger.warning("Excel 第 %s 行用例 %s 的 enabled 为空，按不执行处理", offset, record["case_id"])
            record["enabled"] = "N"
        for field in ("calculate_yaml", "validate_yaml", "accept_yaml"):
            if not record[field]:
                raise ConfigError(f"Excel 第 {offset} 行 {field} 不能为空")
        cases.append(record)

    logger.info("从 %s 读取到 %s 条用例", path, len(cases))
    return cases
