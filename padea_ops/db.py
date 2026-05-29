from __future__ import annotations
from typing import Any
from supabase import create_client, Client
from .config import load_settings

def get_client() -> Client:
    settings = load_settings()
    return create_client(settings.supabase_url, settings.supabase_key)

def fetch_all(client: Client, table: str, *, select: str = "*",
              filters: dict[str, Any] | None = None, order_by: str | None = None,
              ascending: bool = True, limit: int | None = None) -> list[dict[str, Any]]:
    query = client.table(table).select(select)
    if filters:
        for col, value in filters.items():
            query = query.is_(col, "null") if value is None else query.eq(col, value)
    if order_by:
        query = query.order(order_by, desc=not ascending)
    if limit is not None:
        query = query.limit(limit)
    return query.execute().data or []

def upsert_rows(client: Client, table: str, rows: list[dict[str, Any]], *,
                on_conflict: str | None = None) -> list[dict[str, Any]]:
    if not rows:
        return []
    q = client.table(table).upsert(rows, on_conflict=on_conflict) if on_conflict else client.table(table).upsert(rows)
    return q.execute().data or []

def update_rows(client: Client, table: str, values: dict[str, Any], filters: dict[str, Any]) -> list[dict[str, Any]]:
    q = client.table(table).update(values)
    for col, value in filters.items():
        q = q.eq(col, value)
    return q.execute().data or []

def delete_rows(client: Client, table: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
    q = client.table(table).delete()
    for col, value in filters.items():
        q = q.eq(col, value)
    return q.execute().data or []
