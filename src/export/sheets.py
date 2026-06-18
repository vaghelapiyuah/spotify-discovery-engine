"""Spreadsheet export: multi-tab Excel (no setup) or a live Google Sheet.

Both take `frames`: an ordered dict of {tab_name: pandas.DataFrame}.

Google Sheets needs a Google service account (free):
  1. Google Cloud console -> enable "Google Sheets API" + "Google Drive API"
  2. Create a service account -> create a JSON key
  3. Provide the JSON to the app (env GOOGLE_SERVICE_ACCOUNT_JSON, or Streamlit
     secret [gcp_service_account]) and a share email so you can open the sheet.
"""

from __future__ import annotations

import io

import pandas as pd

# Worksheet/tab name cleanup (Excel + Sheets disallow some chars, 31-char cap).
_BAD = set(r"[]:*?/\\")


def _safe_tab(name: str) -> str:
    cleaned = "".join("_" if ch in _BAD else ch for ch in name)
    return cleaned[:31] or "Sheet"


def to_excel_bytes(frames: dict[str, pd.DataFrame]) -> bytes:
    """Build a multi-sheet .xlsx in memory. Works with no credentials."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        used: set[str] = set()
        for name, df in frames.items():
            tab = _safe_tab(name)
            i = 1
            while tab in used:  # ensure uniqueness
                tab = _safe_tab(f"{name}_{i}")
                i += 1
            used.add(tab)
            (df if not df.empty else pd.DataFrame({"info": ["no data"]})).to_excel(
                writer, sheet_name=tab, index=False
            )
    return buf.getvalue()


def export_to_google_sheet(
    frames: dict[str, pd.DataFrame],
    creds_info: dict,
    title: str,
    share_email: str | None = None,
) -> str:
    """Create a Google Sheet with one worksheet per frame; return its URL.

    `creds_info` is the parsed service-account JSON (a dict).
    """
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    gc = gspread.authorize(creds)

    sh = gc.create(title)
    if share_email:
        sh.share(share_email, perm_type="user", role="writer", notify=False)

    first = True
    for name, df in frames.items():
        tab = _safe_tab(name)
        ws = sh.sheet1 if first else sh.add_worksheet(
            title=tab, rows=max(len(df) + 1, 10), cols=max(len(df.columns), 4)
        )
        if first:
            ws.update_title(tab)
            first = False

        if df.empty:
            ws.update([["no data"]])
            continue
        # Header + rows; coerce everything JSON/Sheets-safe.
        values = [list(map(str, df.columns))]
        for row in df.itertuples(index=False):
            values.append([_cell(v) for v in row])
        ws.update(values)

    # Make it link-viewable so it opens on any device.
    try:
        sh.share(None, perm_type="anyone", role="reader", with_link=True)
    except Exception:
        pass  # org policy may forbid; the share_email writer still has access

    return sh.url


def _cell(v):
    if v is None:
        return ""
    if isinstance(v, (int, float, bool, str)):
        return v
    return str(v)
