# -*- coding: utf-8 -*-
"""MySQL 客户端。

出单主流程不调用本模块。需要校验落库数据时，用 DBClient.from_settings() 读取配置。
SQL 必须使用参数化写法，不要用字符串拼接用户输入。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

import pymysql
from pymysql.cursors import DictCursor

from common.exception_util import ConfigError
from config.setting import settings
from encapsulation.logger_handler import get_logger

logger = get_logger("db_client")


class DBClient:
    """基于 pymysql 的增删改查封装。"""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        charset: str = "utf8mb4",
    ) -> None:
        """建立数据库连接。

        入参:
            host: 数据库主机。
            port: 端口。
            user: 用户名。
            password: 密码，允许为空字符串，由数据库本身决定是否接受。
            database: 库名。
            charset: 字符集。
        出参:
            无。
        异常:
            pymysql.MySQLError: 连接失败。异常信息中不记录密码。
        """
        self._config = {
            "host": host,
            "port": port,
            "user": user,
            "database": database,
            "charset": charset,
        }
        logger.info("连接数据库 | host=%s | port=%s | database=%s | user=%s", host, port, database, user)
        try:
            self._connection = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset=charset,
                cursorclass=DictCursor,
                autocommit=True,
                connect_timeout=5,
            )
        except pymysql.MySQLError as exc:
            logger.exception("数据库连接失败 | host=%s | database=%s", host, database)
            raise

    @classmethod
    def from_settings(cls) -> "DBClient":
        """使用 config.yaml 和环境变量创建客户端。

        入参:
            无。
        出参:
            已连接的 DBClient。
        异常:
            ConfigError: 主机、用户或库名为空。
            pymysql.MySQLError: 连接失败。
        """
        cfg = settings.database
        missing = [name for name in ("host", "user", "database") if not str(cfg.get(name) or "").strip()]
        if missing:
            raise ConfigError(
                f"数据库配置缺少 {missing}。请修改 config.yaml，或设置环境变量 DB_HOST、DB_USER、DB_NAME、DB_PASSWORD"
            )
        return cls(
            host=str(cfg["host"]),
            port=int(cfg["port"]),
            user=str(cfg["user"]),
            password=str(cfg.get("password") or ""),
            database=str(cfg["database"]),
            charset=str(cfg.get("charset") or "utf8mb4"),
        )

    def query(self, sql: str, args: Optional[Sequence[Any]] = None) -> List[Dict[str, Any]]:
        """执行查询。

        入参:
            sql: 带占位符的 SELECT 语句，例如 SELECT * FROM t WHERE id=%s。
            args: 参数序列。
        出参:
            字典列表。没有数据时返回空列表。
        异常:
            pymysql.MySQLError: SQL 执行失败。
        """
        logger.info("执行查询 | sql=%s | args=%s", sql, args)
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(sql, args)
                rows = list(cursor.fetchall())
        except pymysql.MySQLError:
            logger.exception("查询失败 | sql=%s", sql)
            raise
        logger.info("查询完成 | 行数=%s", len(rows))
        return rows

    def execute(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        """执行插入、更新或删除。

        入参:
            sql: 带占位符的 SQL。
            args: 参数序列。
        出参:
            受影响的行数。
        异常:
            pymysql.MySQLError: SQL 执行失败。
        """
        logger.info("执行更新 | sql=%s | args=%s", sql, args)
        try:
            with self._connection.cursor() as cursor:
                affected = cursor.execute(sql, args)
        except pymysql.MySQLError:
            logger.exception("更新失败 | sql=%s", sql)
            raise
        logger.info("更新完成 | 影响行数=%s", affected)
        return int(affected)

    def insert(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        """执行插入语句。

        入参:
            sql: INSERT 语句。
            args: 参数序列。
        出参:
            受影响的行数。
        异常:
            pymysql.MySQLError: 执行失败。
        """
        return self.execute(sql, args)

    def update(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        """执行更新语句。

        入参:
            sql: UPDATE 语句。
            args: 参数序列。
        出参:
            受影响的行数。
        异常:
            pymysql.MySQLError: 执行失败。
        """
        return self.execute(sql, args)

    def delete(self, sql: str, args: Optional[Sequence[Any]] = None) -> int:
        """执行删除语句。

        入参:
            sql: DELETE 语句。
            args: 参数序列。
        出参:
            受影响的行数。
        异常:
            pymysql.MySQLError: 执行失败。
        """
        return self.execute(sql, args)

    def close(self) -> None:
        """关闭连接。

        入参:
            无。
        出参:
            无。
        异常:
            无。重复关闭会被忽略。
        """
        connection = getattr(self, "_connection", None)
        if connection is None:
            return
        try:
            connection.close()
            logger.info("数据库连接已关闭 | database=%s", self._config.get("database"))
        except pymysql.MySQLError as exc:
            logger.warning("关闭数据库连接失败：%s", exc)

    def __enter__(self) -> "DBClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
