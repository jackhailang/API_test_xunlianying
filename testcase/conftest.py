# -*- coding: utf-8 -*-
"""pytest 公共夹具。

负责创建输出目录、初始化日志，并为每条用例提供独立的 requests.Session。
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest

# 保证从任意工作目录启动 pytest 时也能导入项目包。
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.allure_report import generate_allure_report
from common.exception_util import ConfigError
from config.setting import LOG_DIR, REPORT_DIR, RESULT_DIR, settings
from encapsulation.http_client import HttpClient
from encapsulation.logger_handler import get_logger, setup_logger

logger = get_logger("conftest")


@pytest.fixture(scope="session", autouse=True)
def prepare_runtime():
    """会话开始时创建输出目录和 Allure 环境信息。

    入参:
        无。
    出参:
        无。
    异常:
        OSError: 输出目录无法创建。
    """
    for directory in (LOG_DIR, REPORT_DIR, RESULT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    setup_logger()
    RESULT_DIR.joinpath("environment.properties").write_text(
        "\n".join(
            [
                f"Environment={settings.env_key}",
                f"EnvironmentName={settings.env_name}",
                f"BaseUrl={settings.base_url}",
                f"Python={platform.python_version()}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    yield


@pytest.fixture
def api_client():
    """为单条用例提供 HTTP 客户端，用例结束时关闭 Session。

    入参:
        无。
    出参:
        HttpClient。
    异常:
        无。
    """
    client = HttpClient()
    yield client
    client.close()


def pytest_sessionfinish(session, exitstatus):
    """全部用例结束后自动生成 Allure HTML 报告。

    入参:
        session: pytest 会话对象。
        exitstatus: 会话退出状态码。
    出参:
        无。报告写入 output/reports/html/时间戳/index.html，不覆盖历史报告。
    异常:
        不向外抛出。生成失败时写入日志，避免覆盖已经完成的测试结果。
    """
    if getattr(session.config.option, "collectonly", False):
        return
    try:
        index_file = generate_allure_report()
    except ConfigError as exc:
        logger.error("自动生成 Allure 报告失败：%s", exc)
        return
    message = f"Allure 报告已生成：{index_file}"
    logger.info(message)
    print(f"\n{message}")
