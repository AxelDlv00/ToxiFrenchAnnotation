import pandas as pd
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import math

def sanitize(value):
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return ""
    return value if value is not None else ""

class GoogleSheetHandler:
    def __init__(self, proxy, sheet_url, secrets):

        if proxy and proxy.strip():
            os.environ["HTTPS_PROXY"] = proxy
            os.environ["HTTP_PROXY"] = proxy

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(secrets, scope)
        client = gspread.authorize(creds)

        self.sheet = client.open_by_url(sheet_url)
        self.worksheet = self.sheet.sheet1

        # Cache header once
        header = self.worksheet.row_values(1)
        self.columns = header if header else []

    def to_pandas(self, types=None):
        values = self.worksheet.get_all_values()
        if not values:
            return pd.DataFrame(columns=self.columns)
        df = pd.DataFrame(columns=values[0], data=values[1:])
        if types:
            for col, dtype in types.items():
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: None if x in ["None", ""] else x)
                    if dtype == float:
                        df[col] = df[col].str.replace(",", ".", regex=False)
                    df[col] = df[col].astype(dtype)
        return df

    def append(self, row: dict):
        assert self.columns, "Sheet has no headers"
        assert all(col in self.columns for col in row), "Row keys must match the sheet columns"
        ordered_row = [sanitize(row.get(col, "")) for col in self.columns]
        self.worksheet.append_row(ordered_row)

    def append_rows(self, rows: list[dict]):
        assert self.columns, "Sheet has no headers"
        prepared_rows = [
            [sanitize(row.get(col, "")) for col in self.columns]
            for row in rows
        ]
        self.worksheet.append_rows(prepared_rows)  # Single API call
