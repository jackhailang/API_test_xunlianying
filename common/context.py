# -*- coding: utf-8 -*-
"""用例上下文。

同一次出单流程里的试算、核保、承保共用一个 context。
接口关联字段只允许通过 YAML extract 写入，调用方不要在步骤代码里写死响应字段。
"""
from __future__ import annotations

from typing import Any, Dict

from common.exception_util import VariableNotFoundError
from common.time_util import build_builtin_variables

# 缺失时给出更明确的排查位置。新增关联字段时可在这里补充提示。
_MISSING_HINTS = {
    "orderId": "请检查核保 YAML 的 extract 配置",
    "totalPremium": "请检查试算 YAML 的 extract 配置",
    "outChannelOrderId": "请检查试算 YAML 的 extract 配置，或确认内置变量已初始化",
}


class Context:
    """保存一条 Excel 用例执行期间的全部变量。"""

    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}

    def init_builtins(self) -> None:
        """写入时间、UUID 和请求侧流水号。

        入参:
            无。
        出参:
            无。
        异常:
            无。
        """
        self._data.update(build_builtin_variables())

    def set(self, key: str, value: Any) -> None:
        """写入或覆盖一个变量。

        入参:
            key: 变量名，对应 YAML 中的 ${变量名}。
            value: 变量值，保留响应里的原始类型。
        出参:
            无。
        异常:
            ValueError: 变量名为空。
        """
        name = str(key).strip()
        if not name:
            raise ValueError("上下文变量名不能为空")
        self._data[name] = value

    def update(self, variables: Dict[str, Any]) -> None:
        """批量写入提取结果。

        入参:
            variables: 本次 extract 得到的变量。
        出参:
            无。
        异常:
            ValueError: 某个变量名为空。
        """
        for key, value in variables.items():
            self.set(key, value)

    def has(self, key: str) -> bool:
        """判断变量是否已经存在。

        入参:
            key: 变量名。
        出参:
            存在返回 True，否则 False。值为 None 也视为存在。
        异常:
            无。
        """
        return key in self._data

    def get(self, key: str) -> Any:
        """读取变量。

        入参:
            key: 变量名。
        出参:
            变量值。
        异常:
            VariableNotFoundError: 变量不存在。
        """
        if key not in self._data:
            hint = _MISSING_HINTS.get(key, "请检查前置接口 YAML 的 extract 配置")
            raise VariableNotFoundError(f"上下文变量 {key} 不存在，{hint}")
        return self._data[key]

    def as_dict(self) -> Dict[str, Any]:
        """返回变量副本，避免替换过程改到上下文。

        入参:
            无。
        出参:
            当前变量字典的浅拷贝。
        异常:
            无。
        """
        return dict(self._data)

    def keys(self) -> list:
        """返回当前变量名列表，用于日志。

        入参:
            无。
        出参:
            变量名列表。
        异常:
            无。
        """
        return list(self._data.keys())
