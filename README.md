# Invoice Automation Tool

A FastAPI web app that reads raw invoice files (CSV/Excel), extracts the office **Location** (SD or AW) and the **Service Description** from the free-text Notes column using regex rules, and returns a summary, a preview and a cleaned Excel file.

## Why this exists

Invoice exports often keep the useful details buried in free-text notes, for example:

> Invoice accounted towards housekeeping charges for the 3rd floor - SD

Turning those notes into structured columns by hand is slow and error-prone. This tool automates it: upload the file, get `Location` and `Service Desc` columns added automatically, and download the cleaned data.

## Features

- Upload one or more `.csv`, `.xls` or `.xlsx` files (drag and drop or browse)
- Combines multiple files into a single dataset
- Normalizes column names automatically (case, underscores and extra spaces)
- Detects the notes column automatically (`notes`, `note`, `description`, `remarks` or `narration`)
- Extracts **Location** (SD / AW) from keywords in the notes
- Extracts **Service Desc** using a chain of regex patterns, then cleans out floor references and trailing month names
- Converts amount columns to numbers (`net amount`, `gst`, `gross amount`, `tds`, `total`)
- Summary cards: original rows, processed rows, SD rows, AW rows, unique services, unique vendors, total amount
- Preview of the first 15 rows with the new columns highlighted
- One-click download of the cleaned data as an Excel file

## How the extraction works

### Location

| Location | Triggered by (case-insensitive) |
|---|---|
| **AW** | `AW`, Angkor West, Bagmane Office, Bagmane Capital, Bagmane Tech Park |
| **SD** | `SD`, Golf Link(s) Software Park, Sunning Dale |
| **SD** (default) | Empty notes, or no keyword matched |

AW keywords are checked first, then SD keywords.

### Service Description

The tool looks for phrases such as:

- "accounted towards charges for `<service>`"
- "invoice accounted towards `<service>`"
- "accounted for the `<service>`"
- "accounting for the `<service>`"
- "recorded the purchase of `<service>`"
- "invoice being accounted for `<service>`"
- "accounted for `<service>`"
- "accounting towards purchase of `<service>`"

The text after the phrase is captured up to the next separator (`-`, `,`, `(`, "as", "for", "from", etc.) and cleaned. If no pattern matches, `Service Desc` is left blank.

## Input requirements

| Column | Required | Notes |
|---|---|---|
| Notes column (`notes` / `note` / `description` / `remarks` / `narration`) | Yes | Source for Location and Service Desc |
| `net amount`, `gst`, `gross amount`, `tds`, `total` | Optional | Converted to numbers if present |
| `vendor name` | Optional | Used for the "Unique Vendors" count |
| Any other columns | Optional | Kept as they are in the output |

Column names are matched case-insensitively, and `_` is treated as a space.

## Output

An Excel file named `Cleaned_Invoice_Data_<timestamp>.xlsx` with a `Cleaned_Data` sheet. `Location` and `Service Desc` appear as the first two columns, followed by all the original columns.

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn
- **Data processing:** pandas, NumPy, openpyxl, `re`
- **Frontend:** single HTML file with inline CSS and JavaScript, Font Awesome icons, DM Sans / DM Mono fonts

## Project structure

```
invoice-automation-tool/
├── main.py             # FastAPI app and extraction logic
├── requirements.txt    # Python dependencies
├── templates/
│   └── index.html      # Web interface
└── static/
```

## Getting started

### Prerequisites

- Python 3.9 or later

### Installation

```bash
# Clone the repository
git clone https://github.com/Akshay-Kumar-S210/invoice-automation-tool.git
cd invoice-automation-tool

# (Optional) create a virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### Run the app

```bash
python main.py
```

Then open **http://localhost:8000** in your browser.

## How to use

1. Open the app in your browser.
2. Drag and drop your invoice files, or click to browse.
3. Click **Process & Clean Data**.
4. Review the summary cards and the preview table.
5. Click **Download Cleaned Excel** to save the result.
6. Click **Process New File** to start again.

## API

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves the web interface |
| `POST` | `/process` | Accepts `data_files` (multipart upload), returns JSON with summary, preview rows and the Excel file as base64 |

FastAPI's interactive docs are available at **http://localhost:8000/docs** while the app is running.

## Notes and limitations

- Rows whose notes match no location keyword are labelled **SD** by default, so check any invoices that should be AW.
- Rows whose notes match no service pattern get a blank `Service Desc`. New note formats may need an extra pattern in `extract_service_desc()` in `main.py`.
- The app is intended for local or internal use. If you deploy it, restrict the CORS settings in `main.py` (currently open to all origins).
