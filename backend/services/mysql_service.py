"""MySQL 持久化服务 - 异步连接池"""

import json
import logging
from typing import Any, Dict, Optional

import aiomysql

logger = logging.getLogger(__name__)


class MySQLService:
    """异步 MySQL 服务，使用连接池管理连接。"""

    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._pool: Optional[aiomysql.Pool] = None

    async def connect(self) -> None:
        """Initialize the connection pool."""
        self._pool = await aiomysql.create_pool(
            host=self._host,
            port=self._port,
            user=self._user,
            password=self._password,
            db=self._database,
            charset="utf8mb4",
            autocommit=True,
            minsize=1,
            maxsize=10,
        )
        # 验证连接
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
        logger.info(f"[MySQL] Connected to {self._host}:{self._port}/{self._database}")

    async def close(self) -> None:
        """Close the connection pool."""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            logger.info("[MySQL] Connection pool closed")

    async def save_company(
        self,
        job_id: str,
        company_url: Optional[str],
        company_name: Optional[str],
        industry: Optional[str],
        hq_location: Optional[str],
    ) -> None:
        """查询时保存公司基本信息。"""
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO companies (job_id, company_url, company_name, industry, hq_location) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (job_id, company_url, company_name, industry, hq_location),
                    )
        except Exception as e:
            logger.error(f"[MySQL] save_company failed: {e}")

    async def save_report(
        self,
        job_id: str,
        company_name: Optional[str],
        report_content: str,
    ) -> None:
        """研究完成后保存最终报告。"""
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO research_reports (job_id, company_name, report_content) "
                        "VALUES (%s, %s, %s)",
                        (job_id, company_name, report_content),
                    )
        except Exception as e:
            logger.error(f"[MySQL] save_report failed: {e}")

    async def save_email(
        self,
        company_name: Optional[str],
        subject: Optional[str],
        body: str,
        email_json: Optional[Dict[str, Any]] = None,
        job_id: Optional[str] = None,
    ) -> None:
        """保存生成的开发信。"""
        if not self._pool:
            return
        try:
            json_str = json.dumps(email_json, ensure_ascii=False) if email_json else None
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO outreach_emails (job_id, company_name, subject, body, email_json) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (job_id, company_name, subject, body, json_str),
                    )
        except Exception as e:
            logger.error(f"[MySQL] save_email failed: {e}")

    async def get_products_by_categories(
        self,
        categories: list[str],
        limit: int = 6,
    ) -> list[Dict[str, Any]]:
        """根据品类列表查询在售产品，返回推荐产品信息。"""
        if not self._pool or not categories:
            return []
        try:
            # 参数化查询防止注入
            placeholders = ",".join(["%s"] * len(categories))
            sql = (
                f"SELECT sku, category, product_name, image_url, advantages, available_colors "
                f"FROM product_catalog "
                f"WHERE is_active = 1 AND category IN ({placeholders}) "
                f"ORDER BY FIELD(category, {placeholders}), tier DESC "
                f"LIMIT %s"
            )
            params = tuple(categories) + tuple(categories) + (limit,)
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params)
                    rows = await cur.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[MySQL] get_products_by_categories failed: {e}")
            return []

    async def get_all_active_products(self, limit: int = 6) -> list[Dict[str, Any]]:
        """查询所有在售产品（兜底用）。"""
        if not self._pool:
            return []
        try:
            sql = (
                "SELECT sku, category, product_name, image_url, advantages, available_colors "
                "FROM product_catalog "
                "WHERE is_active = 1 "
                "ORDER BY tier DESC "
                "LIMIT %s"
            )
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, (limit,))
                    rows = await cur.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"[MySQL] get_all_active_products failed: {e}")
            return []

    async def get_available_categories(self) -> list[str]:
        """查询数据库中实际有在售产品的品类列表。"""
        if not self._pool:
            return []
        try:
            sql = (
                "SELECT DISTINCT category FROM product_catalog WHERE is_active = 1 ORDER BY category"
            )
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql)
                    rows = await cur.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"[MySQL] get_available_categories failed: {e}")
            return []
