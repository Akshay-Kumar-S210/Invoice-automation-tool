from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import numpy as np
import io
import base64
import re
from datetime import datetime
import os
from typing import List, Dict, Any

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize column names for easier matching."""
    df.columns = [c.strip().lower().replace("_", " ") for c in df.columns]
    return df


def safe_float(value):
    try:
        return float(str(value).replace(",", "").strip())
    except Exception:
        return 0.0


def extract_service_desc(notes: str) -> str:
    """
    Extract the service description from Notes column.
    Looks for text after patterns like:
      - "Accounted towards <service>"
      - "Invoice accounted towards <service>"
      - "accounted towards charges for <service>"
      - "Accounted for the<service>"
    Returns the key service name found.
    """
    if pd.isna(notes) or not str(notes).strip():
        return ""

    notes_str = str(notes).strip()

    # Pattern: "accounted towards charges for <service>"
    match = re.search(
        r"accounted\s+towards\s+charges\s+for\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+for\s|\s+from\s|$)",
        notes_str,
        re.IGNORECASE,
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)

    # Pattern: "invoice accounted towards <service>" OR "accounted towards <service>"
    match = re.search(
        r"(?:invoice\s+)?accounted\s+towards\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+for\s|\s+from\s|\s+\d{1,2}[a-z]{2}\s+floor|$)",
        notes_str,
        re.IGNORECASE,
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Accounted for the<service>"
    match = re.search( 
         r"accounted\s+for\s+the\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+for\s|\s+from\s|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Accounting for the purchase of <service>"
    match = re.search( 
         r"accounting\s+for\s+the\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+under\s|\s+for\s|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Recorded the purchase of <service>"
    match = re.search( 
         r"recorded\s+the\s+(purchase\s+of\s+.+?)(?:\s*[-–,\(]|\s+under\s|\s+for\s|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Invoice being Accounted for <service>"
    match = re.search( 
         r"invoice\s+being\s+accounted\s+for\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+for\s|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Accounted for <service>" (general fallback)"
    match = re.search( 
          r"accounted\s+for\s+(.+?)(?:\s*[-–,\(]|\s+as\s|\s+for\s|\s+from\s|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)
     # Pattern: "Accounting towards purchase of <service>" (general fallback)"
    match = re.search( 
          r"accounting\s+towards\s+purchase\s+of\s+(.+?)(?:\s+with\s|\s+along\s|\s+for\s|\s+as\s|\s*[-–,\(]|$)",
        notes_str,
        re.IGNORECASE,                                      
    )
    if match:
        raw = match.group(1).strip().rstrip(".,;:-")
        return _clean_service_name(raw)

    return ""


def _clean_service_name(name: str) -> str:
    """Strip trailing boilerplate words / date artifacts from a service name."""
    # Remove trailing floor references like "(3rd floor)", "(Ground floor)" etc.
    name = re.sub(r"\s*\(\s*\w+\s+floor\s*\)", "", name, flags=re.IGNORECASE)
    # Remove trailing month references like "for April", "for March 2025"
    name = re.sub(
        r"\s+for\s+(january|february|march|april|may|june|july|august|september|october|november|december)(\s+\d{4})?$",
        "",
        name,
        flags=re.IGNORECASE,
    )
    # Remove trailing "(Xnd / Xrd / Xth floor)"
    name = re.sub(r"\s*\d+(?:st|nd|rd|th)\s+floor", "", name, flags=re.IGNORECASE)
    return name.strip().rstrip(".,;:-")


def extract_location(notes: str) -> str:
    """
    Derive Location from Notes column.
    Rules:
      - Contains "SD", "Golf Link Software Park", or "Sunning Dale" → SD
      - Contains "Bagmane Office", "AW", "Bagmane Capital"          → AW
      - Default → SD
    """
    if pd.isna(notes) or not str(notes).strip():
        return "SD"

    notes_str = str(notes)

    # AW indicators (check before SD to avoid false positives)
    aw_patterns = [
        r"\bAW\b",
        r" Angkor\s+West",
        r"Bagmane\s+Office",
        r"Bagmane\s+Capital",
        r"Bagmane\s+Tech\s+Park",
    ]
    for pat in aw_patterns:
        if re.search(pat, notes_str, re.IGNORECASE):
            return "AW"

    # SD indicators
    sd_patterns = [
        r"\bSD\b",
        r"Golf\s+Link[s]?\s+Software\s+Park",
        r"Sunning\s*Dale",
    ]
    for pat in sd_patterns:
        if re.search(pat, notes_str, re.IGNORECASE):
            return "SD"

    return "SD"  # default


def convert_numpy(obj):
    """Convert NumPy/datetime objects to JSON-safe types."""
    if isinstance(obj, (np.integer, np.int32, np.int64)):
        return int(obj)
    if isinstance(obj, (np.floating, np.float32, np.float64)):
        return float(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.strftime("%Y-%m-%d")
    if pd.isna(obj):
        return None
    return obj


def calculate_summary(original_df: pd.DataFrame, processed_df: pd.DataFrame) -> Dict[str, Any]:
    """Build UI summary statistics."""
    sd_count = int((processed_df["location"] == "SD").sum()) if "location" in processed_df.columns else 0
    aw_count = int((processed_df["location"] == "AW").sum()) if "location" in processed_df.columns else 0
    unique_services = processed_df["service desc"].nunique() if "service desc" in processed_df.columns else 0
    total_amount = processed_df["total"].sum() if "total" in processed_df.columns else (
        processed_df["gross amount"].sum() if "gross amount" in processed_df.columns else 0
    )
    unique_vendors = processed_df["vendor name"].nunique() if "vendor name" in processed_df.columns else (
        processed_df["vendor_name"].nunique() if "vendor_name" in processed_df.columns else 0
    )

    summary = {
        "original_rows": len(original_df),
        "processed_rows": len(processed_df),
        "sd_count": sd_count,
        "aw_count": aw_count,
        "unique_services": int(unique_services),
        "unique_vendors": int(unique_vendors),
        "total_amount": float(total_amount),
    }
    return summary


@app.post("/process")
async def process_file(data_files: List[UploadFile] = File(...)):
    try:
        if not data_files:
            return JSONResponse({"success": False, "error": "No files uploaded"}, status_code=400)

        df_combined = pd.DataFrame()

        for file in data_files:
            contents = await file.read()
            name = file.filename.lower()

            if name.endswith(".csv"):
                temp = pd.read_csv(io.BytesIO(contents))
            elif name.endswith((".xls", ".xlsx")):
                temp = pd.read_excel(io.BytesIO(contents))
            else:
                return JSONResponse(
                    {"success": False, "error": f"Unsupported file type: {name}. Please upload .csv or .xlsx/.xls files."},
                    status_code=400,
                )

            temp = normalize_columns(temp)
            df_combined = pd.concat([df_combined, temp], ignore_index=True)

        # Detect notes column (flexible naming)
        notes_col = None
        for candidate in ["notes", "note", "description", "remarks", "narration"]:
            if candidate in df_combined.columns:
                notes_col = candidate
                break

        if notes_col is None:
            return JSONResponse(
                {"success": False, "error": "Could not find a 'Notes' column. Expected column names: notes, note, description, remarks, narration."},
                status_code=400,
            )

        # ------------------------------------------------------------------
        # Core transformation: derive Location & Service_Desc from Notes
        # ------------------------------------------------------------------
        df_combined["location"] = df_combined[notes_col].apply(extract_location)
        df_combined["service desc"] = df_combined[notes_col].apply(extract_service_desc)

        # Normalize numeric columns if present
        for col in ["net amount", "gst", "gross amount", "tds", "total"]:
            if col in df_combined.columns:
                df_combined[col] = df_combined[col].apply(safe_float)

        # ------------------------------------------------------------------
        # Build output column order — keep original columns, replace/add derived
        # Remove old location / service_desc columns if they existed (they'll be
        # replaced by our derived versions at the front)
        # ------------------------------------------------------------------
        derived_cols = ["location", "service desc"]
        other_cols = [c for c in df_combined.columns if c not in derived_cols]
        output_df = df_combined[derived_cols + other_cols].copy()

        # Pretty-print column names for output (Title Case)
        output_df.columns = [c.title() for c in output_df.columns]

        summary = calculate_summary(df_combined, df_combined)

        # Preview — first 15 rows
        preview = output_df.head(15).copy()
        preview = preview.where(preview.notna(), other=None)
        preview_records = []
        for _, row in preview.iterrows():
            preview_records.append({k: convert_numpy(v) for k, v in row.items()})

        # Build downloadable Excel
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            output_df.to_excel(writer, index=False, sheet_name="Cleaned_Data")
        encoded = base64.b64encode(excel_buf.getvalue()).decode("utf-8")
        filename = f"Cleaned_Invoice_Data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return JSONResponse(
            {
                "success": True,
                "summary": summary,
                "preview_data": preview_records,
                "filename": filename,
                "file_data": encoded,
                "message": f"Successfully cleaned {summary['processed_rows']} rows — Location & Service Desc extracted from Notes.",
            }
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse({"success": False, "error": str(e)}, status_code=500)


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the web interface."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
