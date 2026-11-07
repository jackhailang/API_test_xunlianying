# -*- coding: utf-8 -*-
"""Allure HTML 报告生成。

pytest 只负责把原始结果写到 output/results。
本模块在测试会话结束后调用本机的 allure 命令行生成 HTML。
Windows 下 IDE 或脚本进程的 PATH 可能没刷新，因此同时读取注册表里的用户和系统 Path。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from common.exception_util import ConfigError
from config.setting import REPORT_DIR, RESULT_DIR
from encapsulation.logger_handler import get_logger

logger = get_logger("allure_report")

_HTML_ROOT = REPORT_DIR / "html"
# 目录名示例：20261106_002630 或同一秒冲突时的 20261106_002630_123456。
_REPORT_DIR_PATTERN = re.compile(r"^\d{8}_\d{6}(?:_\d+)?$")


def _registry_path_entries() -> List[str]:
    """读取 Windows 用户和系统 Path。

    入参:
        无。
    出参:
        注册表中的路径列表。非 Windows 返回空列表。
    异常:
        无。注册表不可读时忽略对应项。
    """
    if sys.platform != "win32":
        return []
    import winreg

    entries: List[str] = []
    locations = (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    )
    for root, subkey in locations:
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        entries.extend(str(value).split(";"))
    return entries


def _search_directories() -> List[Path]:
    """合并当前进程 PATH 和注册表 PATH，并去掉重复目录。

    入参:
        无。
    出参:
        可执行文件搜索目录。
    异常:
        无。
    """
    raw_entries = os.environ.get("PATH", "").split(os.pathsep)
    raw_entries.extend(_registry_path_entries())
    directories: List[Path] = []
    seen = set()
    for entry in raw_entries:
        text = entry.strip().strip('"')
        if not text:
            continue
        directory = Path(os.path.expandvars(text))
        marker = os.path.normcase(str(directory))
        if marker in seen:
            continue
        seen.add(marker)
        directories.append(directory)
    return directories


def _find_executable(names: List[str]) -> Optional[Path]:
    """按名称查找可执行文件。

    入参:
        names: 文件名候选，按优先级排列，例如 allure.bat、allure。
    出参:
        找到的文件路径。找不到返回 None。
    异常:
        无。
    """
    for directory in _search_directories():
        for name in names:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def _command_environment(java_executable: Path) -> Dict[str, str]:
    """构造能同时找到 Java 和 Allure 的子进程环境变量。

    入参:
        java_executable: java.exe 或 java 的路径。
    出参:
        环境变量字典。
    异常:
        无。
    """
    env = os.environ.copy()
    java_bin = str(java_executable.parent)
    java_home = str(java_executable.parent.parent)
    merged_path = os.pathsep.join([java_bin, env.get("PATH", "")])
    env["PATH"] = merged_path
    env["JAVA_HOME"] = java_home
    return env


def _timestamp_report_dir(report_root: Path) -> Path:
    """按当前时间生成一个不会覆盖历史报告的目录。

    入参:
        report_root: 报告根目录，下面每个时间戳目录各自保存一份 index.html。
    出参:
        新的报告目录。同一秒内重复生成时会追加微秒。
    异常:
        无。
    """
    current = datetime.now()
    candidate = report_root / current.strftime("%Y%m%d_%H%M%S")
    if not candidate.exists():
        return candidate
    return report_root / current.strftime("%Y%m%d_%H%M%S_%f")


def _write_history_page(report_root: Path) -> Path:
    """刷新历史报告入口页，不改动各次生成的 index.html。

    入参:
        report_root: 报告根目录。
    出参:
        history.html 的路径。
    异常:
        OSError: 入口页无法写入。
    """
    report_dirs = [
        path
        for path in report_root.iterdir()
        if path.is_dir() and _REPORT_DIR_PATTERN.match(path.name) and (path / "index.html").is_file()
    ]
    report_dirs.sort(key=lambda path: path.name, reverse=True)
    items = "\n".join(
        f'<li><a href="{path.name}/index.html">{path.name}</a></li>'
        for path in report_dirs
    )
    if not items:
        items = "<li>暂无历史报告</li>"
    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Allure 历史报告</title>
</head>
<body>
  <h1>Allure 历史报告</h1>
  <p>每次执行单独保存一份 index.html，目录名是生成时间。</p>
  <ul>
    {items}
  </ul>
</body>
</html>
"""
    history_file = report_root / "history.html"
    history_file.write_text(page, encoding="utf-8")
    return history_file


def generate_allure_report(results_dir: Path | None = None, report_dir: Path | None = None) -> Path:
    """根据 Allure 原始结果生成 HTML 报告。

    入参:
        results_dir: 原始结果目录，默认 output/results。
        report_dir: 本次 HTML 目录。为空时使用 output/reports/html/时间戳，避免覆盖历史报告。
    出参:
        本次报告首页 index.html 的路径。
    异常:
        ConfigError: 找不到 Java、Allure，或结果目录没有测试结果。
        subprocess.CalledProcessError: allure generate 执行失败。
    """
    source = Path(results_dir) if results_dir else RESULT_DIR
    target = Path(report_dir) if report_dir else _timestamp_report_dir(_HTML_ROOT)
    result_files = list(source.glob("*-result.json"))
    if not result_files:
        raise ConfigError(f"没有可生成报告的 Allure 结果：{source}")

    java_executable = _find_executable(["java.exe", "java"])
    if java_executable is None:
        raise ConfigError(
            "未在当前进程 PATH、用户 Path 或系统 Path 中找到 java.exe。"
            "请确认 Java 已安装，并且安装目录已写入 Path 或 JAVA_HOME。"
        )

    allure_executable = _find_executable(["allure.bat", "allure.cmd", "allure"])
    if allure_executable is None:
        raise ConfigError(
            "未在当前进程 PATH、用户 Path 或系统 Path 中找到 allure 命令。"
            "请安装 Allure Commandline，并把 bin 目录写入 Path。"
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    env = _command_environment(java_executable)
    if sys.platform == "win32":
        # allure.bat 需要交给 cmd 执行，直接启动批处理文件会找不到 Java。
        command = [
            "cmd.exe",
            "/c",
            str(allure_executable),
            "generate",
            str(source),
            "-o",
            str(target),
        ]
    else:
        command = [str(allure_executable), "generate", str(source), "-o", str(target)]
    logger.info("开始生成 Allure 报告 | java=%s | allure=%s", java_executable, allure_executable)
    completed = subprocess.run(
        command,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise ConfigError(f"Allure 报告生成失败，退出码 {completed.returncode}。{detail}")

    index_file = target / "index.html"
    if not index_file.exists():
        raise ConfigError(f"Allure 命令已执行，但没有找到报告首页：{index_file}")
    history_file = _write_history_page(_HTML_ROOT)
    logger.info("Allure 报告已生成：%s", index_file)
    logger.info("历史报告入口：%s", history_file)
    return index_file
