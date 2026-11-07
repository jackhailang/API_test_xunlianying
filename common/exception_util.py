# -*- coding: utf-8 -*-
"""框架异常。

业务失败信息使用中文，方便日志和 Allure 直接定位是配置、变量、提取还是请求问题。
"""


class FrameworkException(Exception):
    """框架基础异常。其他异常都从这里派生。"""


class ConfigError(FrameworkException):
    """配置文件、Excel 列或 YAML 必填项不合法。"""


class VariableNotFoundError(FrameworkException):
    """请求报文引用了上下文中不存在的 ${变量名}。"""


class ExtractError(FrameworkException):
    """按 YAML 的 extract 路径从响应中取值失败。"""


class RequestError(FrameworkException):
    """HTTP 调用在收到业务响应之前失败，例如超时、连接失败。"""

    def __init__(self, message: str, method: str = "", url: str = "") -> None:
        """记录失败请求的方法和地址。

        入参:
            message: 给测试人员看的失败原因。
            method: 请求方法，可能为空。
            url: 完整请求地址，可能为空。
        出参:
            无。
        异常:
            无。本方法只保存信息。
        """
        super().__init__(message)
        self.method = method
        self.url = url
