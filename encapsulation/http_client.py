# -*- coding: utf-8 -*-
"""HTTP 客户端。

基于 requests.Session 复用连接。只封装 GET 和 POST。
核保、承保默认不重试，避免超时后重复出单。
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

import requests

from common.exception_util import ConfigError, RequestError
from config.setting import settings
from encapsulation.logger_handler import get_logger

logger = get_logger("http_client")


class ApiResult:
    """一次 HTTP 调用的结果，供提取变量和断言使用。"""

    def __init__(
        self,
        method: str,
        url: str,
        status_code: int,
        text: str,
        json_data: Any,
        elapsed_ms: float,
        headers: Dict[str, str],
    ) -> None:
        self.method = method
        self.url = url
        self.status_code = status_code
        self.text = text
        self.json_data = json_data
        self.elapsed_ms = elapsed_ms
        self.headers = headers


class HttpClient:
    """线程内复用的 Session 客户端。每个用例结束后由夹具关闭。"""

    def __init__(self, base_url: str | None = None, timeout: int | None = None) -> None:
        """创建 Session。

        入参:
            base_url: 环境根地址。为空时使用当前配置。
            timeout: 默认超时秒数。为空时使用当前配置。
        出参:
            无。
        异常:
            无。
        """
        self.base_url = (base_url if base_url is not None else settings.base_url).rstrip("/")
        self.timeout = settings.timeout if timeout is None else timeout
        self.session = requests.Session()

    def _build_url(self, url: str) -> str:
        """相对路径拼接 base_url，绝对路径保持不变。

        入参:
            url: YAML 中的 url。
        出参:
            完整请求地址。
        异常:
            ConfigError: 使用相对路径但没有 base_url。
        """
        text = "" if url is None else str(url).strip()
        if not text:
            raise ConfigError("请求 URL 不能为空")
        lowered = text.lower()
        if lowered.startswith("http://") or lowered.startswith("https://"):
            return text
        if not self.base_url:
            raise ConfigError(f"相对路径 {text} 无法拼接，当前环境没有 base_url")
        return self.base_url.rstrip("/") + "/" + text.lstrip("/")

    @staticmethod
    def _dump(data: Any) -> str:
        """把请求或响应格式化成日志文本。

        入参:
            data: 任意对象。
        出参:
            JSON 文本。过长时截断，完整内容仍由 Allure 附件保存。
        异常:
            无。
        """
        try:
            text = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        except TypeError:
            text = str(data)
        if len(text) > 5000:
            return text[:5000] + "\n...(日志已截断，完整报文见 Allure)"
        return text

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> ApiResult:
        """发送 HTTP 请求并记录请求、响应和耗时。

        入参:
            method: GET 或 POST。
            url: 相对或绝对地址。
            headers: 请求头。
            json_body: JSON 请求体。
            params: 查询参数。
            timeout: 本次请求超时秒数，为空时用客户端默认值。
        出参:
            ApiResult，包含状态码、原文、JSON、耗时和最终 URL。
        异常:
            ConfigError: 方法不是 GET/POST，或 URL 为空。
            RequestError: 超时、连接失败或其他 requests 异常。
        """
        http_method = str(method or "").strip().upper()
        if http_method not in {"GET", "POST"}:
            raise ConfigError(f"暂只支持 GET 和 POST，当前方法：{method}")

        final_url = self._build_url(url)
        final_timeout = self.timeout if timeout is None else timeout
        logger.info("请求开始 | %s | %s | timeout=%ss", http_method, final_url, final_timeout)
        logger.info("请求头 | %s", self._dump(headers or {}))
        logger.info("请求报文 | %s", self._dump(json_body))

        try:
            response = self.session.request(
                method=http_method,
                url=final_url,
                headers=headers,
                json=json_body,
                params=params,
                timeout=final_timeout,
            )
        except requests.Timeout as exc:
            message = f"请求超时：{http_method} {final_url}，timeout={final_timeout}s"
            logger.exception(message)
            raise RequestError(message, http_method, final_url) from exc
        except requests.ConnectionError as exc:
            message = f"连接失败：{http_method} {final_url}，请检查 base_url、网络或服务是否启动。原因：{exc}"
            logger.exception(message)
            raise RequestError(message, http_method, final_url) from exc
        except requests.RequestException as exc:
            message = f"请求异常：{http_method} {final_url}。原因：{exc}"
            logger.exception(message)
            raise RequestError(message, http_method, final_url) from exc

        elapsed_ms = response.elapsed.total_seconds() * 1000
        try:
            json_data = response.json()
        except ValueError:
            json_data = None

        logger.info(
            "响应结束 | %s | status=%s | 耗时=%.2fms",
            final_url,
            response.status_code,
            elapsed_ms,
        )
        logger.info("响应报文 | %s", self._dump(json_data if json_data is not None else response.text))

        return ApiResult(
            method=http_method,
            url=final_url,
            status_code=response.status_code,
            text=response.text,
            json_data=json_data,
            elapsed_ms=elapsed_ms,
            headers={key: value for key, value in response.headers.items()},
        )

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        timeout: Optional[int] = None,
    ) -> ApiResult:
        """发送 GET 请求。

        入参:
            url: 相对或绝对地址。
            headers: 请求头。
            params: 查询参数。
            json_body: 可选 JSON 请求体。
            timeout: 超时秒数。
        出参:
            ApiResult。
        异常:
            RequestError: 请求没有拿到响应。
            ConfigError: URL 不合法。
        """
        return self.request(
            "GET",
            url,
            headers=headers,
            json_body=json_body,
            params=params,
            timeout=timeout,
        )

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, Any]] = None,
        json_body: Any = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
    ) -> ApiResult:
        """发送 POST 请求。

        入参:
            url: 相对或绝对地址。
            headers: 请求头。
            json_body: JSON 请求体。
            params: 查询参数。
            timeout: 超时秒数。
        出参:
            ApiResult。
        异常:
            RequestError: 请求没有拿到响应。
            ConfigError: URL 不合法。
        """
        return self.request(
            "POST",
            url,
            headers=headers,
            json_body=json_body,
            params=params,
            timeout=timeout,
        )

    def close(self) -> None:
        """关闭 Session，释放连接池。

        入参:
            无。
        出参:
            无。
        异常:
            无。关闭失败只记日志，不掩盖用例结果。
        """
        try:
            self.session.close()
        except Exception as exc:  # noqa: BLE001  关闭连接不应覆盖用例失败原因
            logger.warning("关闭 HTTP Session 时出现异常：%s", exc)
