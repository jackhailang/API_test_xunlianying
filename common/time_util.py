# -*- coding: utf-8 -*-
"""时间与内置变量。

这些变量由框架在每条用例开始时生成，不代表接口响应字段。
接口返回的订单号、保费必须通过 YAML 的 extract 写入上下文。
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime
from typing import Dict


def today(current: datetime | None = None) -> str:
    """返回日期字符串。

    入参:
        current: 指定时间。为空时取本机当前时间。
    出参:
        yyyy-MM-dd 格式的日期。
    异常:
        无。
    """
    value = current or datetime.now()
    return value.strftime("%Y-%m-%d")


def now_time(current: datetime | None = None) -> str:
    """返回时间字符串。

    入参:
        current: 指定时间。为空时取本机当前时间。
    出参:
        HH:mm:ss 格式的时间。
    异常:
        无。
    """
    value = current or datetime.now()
    return value.strftime("%H:%M:%S")


def timestamp(current: datetime | None = None) -> str:
    """返回毫秒时间戳字符串。

    入参:
        current: 指定时间。为空时取本机当前时间。
    出参:
        13 位左右的毫秒时间戳字符串。
    异常:
        无。
    """
    value = current or datetime.now()
    return str(int(value.timestamp() * 1000))


def new_uuid() -> str:
    """返回随机 UUID 字符串。

    入参:
        无。
    出参:
        标准 UUID 文本，例如 916a1298-fad0-4651-b3e0-17726bd93ed5。
    异常:
        无。
    """
    return str(uuid.uuid4())


def numeric_sn(length: int = 20) -> str:
    """生成指定长度的数字流水号。

    入参:
        length: 位数，至少 1 位。
    出参:
        不以 0 开头的数字字符串。
    异常:
        ValueError: 长度小于 1。
    """
    if length < 1:
        raise ValueError("流水号长度必须大于 0")
    first = str(random.randint(1, 9))
    if length == 1:
        return first
    rest = "".join(str(random.randint(0, 9)) for _ in range(length - 1))
    return first + rest


def build_builtin_variables(current: datetime | None = None) -> Dict[str, str]:
    """组装一条用例开始时就具备的内置变量。

    入参:
        current: 指定时间，便于测试；业务执行时不传。
    出参:
        变量字典。后继接口的 extract 如果使用同名变量，会覆盖这里的值。
    异常:
        无。
    """
    moment = current or datetime.now()
    return {
        "today": today(moment),
        "now_time": now_time(moment),
        "timestamp": timestamp(moment),
        "uuid": new_uuid(),
        # 以下三个流水号只是请求侧示例单号。若真实值来自上一接口，请在 YAML extract 中同名覆盖。
        "outChannelOrderId": numeric_sn(20),
        "bkSerial": numeric_sn(18),
        "orderNo": numeric_sn(18),
    }
