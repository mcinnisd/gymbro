from typing import Optional

from app.config import Config
from supabase import create_client, Client


def is_missing_relation_error(exc: BaseException, table: Optional[str] = None) -> bool:
    """
    True for PostgREST PGRST205 / Postgres 42P01 missing-table errors.

    Live example: Could not find the table 'public.lab_panels' in the schema cache
    """
    code = str(
        getattr(exc, "code", "")
        or getattr(exc, "status", "")
        or ""
    ).upper()
    parts = [str(exc), code]
    for attr in ("message", "details", "hint"):
        val = getattr(exc, attr, None)
        if val:
            parts.append(str(val))
    blob = " ".join(parts).lower()
    if code in {"PGRST205", "42P01"} or "pgrst205" in blob or "42p01" in blob:
        if table is None:
            return True
        return table.lower() in blob
    if "schema cache" in blob and "could not find the table" in blob:
        return table is None or table.lower() in blob
    if "does not exist" in blob and ("relation" in blob or "table" in blob):
        return table is None or table.lower() in blob
    return False

url: str = Config.SUPABASE_URL
key: str = Config.SUPABASE_KEY
mock_db: bool = Config.MOCK_DB

if mock_db:
    from app.mock_supabase import MockSupabaseClient
    supabase = MockSupabaseClient()
elif url and key:
    supabase: Client = create_client(url, key)
else:
    supabase = None
