# -*- coding: utf-8 -*-
"""生成保险用例 Excel。

Excel 是二进制文件，因此用本脚本创建 testdata/insurance_cases.xlsx。
重复执行会覆盖原文件。
"""
from __future__ import annotations

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.excel_util import EXCEL_HEADERS
from config.setting import CASE_EXCEL_PATH

# 示例用例。新增流程时追加一行，并准备对应的三个 YAML。
CASE_ROWS = [
    {
        "case_id": "INS001",
        "case_name": "保险出单全流程",
        "calculate_yaml": "Transaction/calculate.yaml",
        "validate_yaml": "Transaction/validate.yaml",
        "accept_yaml": "Transaction/accept.yaml",
        "enabled": "Y",
        "description": "试算核保承保串联",
    },
    {
        "case_id": "INS002",
        "case_name": "禁用示例",
        "calculate_yaml": "Transaction/calculate.yaml",
        "validate_yaml": "Transaction/validate.yaml",
        "accept_yaml": "Transaction/accept.yaml",
        "enabled": "N",
        "description": "enabled 不是 Y 时跳过，不会发送请求",
    },
]


def create_case_excel(target: Path | None = None) -> Path:
    """创建用例 Excel。

    入参:
        target: 输出路径。为空时写到 testdata/insurance_cases.xlsx。
    出参:
        实际写入的文件路径。
    异常:
        OSError: 目录不可写或文件被占用。
    """
    path = Path(target) if target else CASE_EXCEL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "insurance_cases"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True, name="微软雅黑", size=11)
    body_font = Font(name="微软雅黑", size=11)
    alignment = Alignment(vertical="center", wrap_text=True)

    for column, header in enumerate(EXCEL_HEADERS, start=1):
        cell = sheet.cell(1, column, header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = alignment

    for row_index, record in enumerate(CASE_ROWS, start=2):
        for column, header in enumerate(EXCEL_HEADERS, start=1):
            cell = sheet.cell(row_index, column, record[header])
            cell.font = body_font
            cell.alignment = alignment

    enabled_column = get_column_letter(EXCEL_HEADERS.index("enabled") + 1)
    validation = DataValidation(type="list", formula1='"Y,N"', allow_blank=False)
    validation.error = "enabled 只允许 Y 或 N"
    validation.errorTitle = "非法取值"
    validation.add(f"{enabled_column}2:{enabled_column}200")
    sheet.add_data_validation(validation)

    widths = {
        "case_id": 16,
        "case_name": 24,
        "calculate_yaml": 36,
        "validate_yaml": 36,
        "accept_yaml": 34,
        "enabled": 12,
        "description": 40,
    }
    for column, header in enumerate(EXCEL_HEADERS, start=1):
        sheet.column_dimensions[get_column_letter(column)].width = widths[header]

    sheet.auto_filter.ref = f"A1:{get_column_letter(len(EXCEL_HEADERS))}1"
    sheet.freeze_panes = "A2"
    sheet.row_dimensions[1].height = 22
    workbook.save(path)
    return path


if __name__ == "__main__":
    output = create_case_excel()
    print(f"用例 Excel 已生成：{output}")
