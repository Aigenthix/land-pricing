import os
import io
import tempfile
import json
import re
import math
import pathlib
from datetime import datetime
from typing import List, Dict, Tuple, Optional

import pandas as pd
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from dotenv import load_dotenv
import google.generativeai as genai

# ----------------------
# Configuration & Paths
# ----------------------
# We still use the existing Word template for consistent styling
WORD_TEMPLATE_FILE = "index2/format.docx"

# Model name is hardcoded to match index2-word_converter.py
GEMINI_MODEL_NAME = "models/gemini-2.5-pro"


def load_api_key():
    """Load GOOGLE_API_KEY from .env and configure the Gemini client."""
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not found. Create a .env with GOOGLE_API_KEY=<your_key>.")
    genai.configure(api_key=api_key)


def get_multipage_extraction_prompt():
    """Returns the same detailed prompt as in index2-word_converter.py (unchanged)."""
    return """
    Analyze the entire provided multi-page Marathi PDF document. Find ALL pages that are
    formatted as 'Index-II' (सूची क्र.2).

    **CRITICAL INSTRUCTIONS:**
    1.  **Identify and Process ONLY 'Index-II' pages.** These pages contain numbered
        fields like '(1)विलेखाचा प्रकार', '(5)क्षेत्रफळ', etc.
    2.  **Explicitly IGNORE irrelevant pages.** Completely skip any pages titled
        'Payment Details' or any pages that primarily consist of a table of financial
        transactions. Do not extract any data from them.
    3.  **Return a JSON array.** The final output must be a single JSON array (a list
        of objects), where each JSON object represents the data extracted from ONE
        'Index-II' page.
    4.  If no 'Index-II' pages are found, return an empty array `[]`.

    **For each 'Index-II' page found, extract the following fields into a JSON object:**
    -   `dast_kramank_year`: The year part of 'दस्त क्रमांक'.
    -   `sub_registrar_number`: The number at the end of 'दुय्यम निबंधक'.
    -   `dast_kramank_full`: The full value of 'दस्त क्रमांक'.
    -   `registration_date`: The value for '(10)दस्त नोंदणी केल्याचा दिनांक'.
    -   `document_type`: The value for '(1)विलेखाचा प्रकार'.
    -   `survey_number`: All the numbers inside the double parentheses `((...))` from section (4),
        like 'Survey Number'. Some numbers can have parts to them (for example 1ब, 2ब)
    -   `area_sq_meter`: The value for '(5)क्षेत्रफळ'. VERY IMPORTANT: First, try to extract the area from '(5)क्षेत्रफळ'. If the value is 0, missing, or empty, you MUST read the text in section '(4) भू-मापन, पोटहिस्सा...'. When reading section (4), look for the absolute largest parent plot area mentioned before the fraction or share breakdown. Specifically, look for phrases like "एकूण क्षेत्रफळ" (Total Area) or the number immediately preceding the word "पैकी" (which means 'out of'). Do NOT extract the smaller fractional share. Convert units if necessary: 'चौ.फुट'*0.092903, 'हेक्टर'*10000. If 'चौ.मीटर' or 'चौ.मी', use directly. Return only the final numerical value.
    -   `stamp_duty`: The value for '(12)बाजारभावाप्रमाणे मुद्रांक शुल्क'.
    -   `amount`: The value for '(2) मोबदला'. Return only the numeric value (no currency symbols).

    Return ONLY the JSON array and nothing else.
    """


def clean_and_convert_to_float(value, default=0.0):
    if value is None:
        return default
    try:
        cleaned_value = re.sub(r"[^0-9.]", "", str(value))
        return float(cleaned_value) if cleaned_value else default
    except (ValueError, TypeError):
        return default


# --- Helpers for Survey Number normalization ---

def _is_digit_char(c: str) -> bool:
    return ("0" <= c <= "9") or ("\u0966" <= c <= "\u096F")


def _is_numeric_token(token: str) -> bool:
    token = (token or "").strip()
    if not token:
        return False
    return all(_is_digit_char(ch) for ch in token)


def _starts_with_number(token: str) -> bool:
    token = (token or "").strip()
    return bool(token) and _is_digit_char(token[0])


def normalize_survey_numbers(value) -> str:
    items = None
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        txt = value.strip()
        if txt.startswith("[") and txt.endswith("]"):
            try:
                parsed = json.loads(txt)
                if isinstance(parsed, list):
                    items = [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                items = None
        if items is None:
            if "," in txt:
                items = [s.strip() for s in txt.split(",") if s.strip()]
            else:
                return txt
    else:
        return str(value)

    out = []
    last_base = None
    for tok in items:
        if _is_numeric_token(tok):
            last_base = tok
            out.append(tok)
        elif _starts_with_number(tok) and last_base:
            out.append(f"{last_base} {tok}")
        else:
            out.append(tok)
    return ", ".join(out)


def add_table_borders(table):
    tbl = table._element
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border_el = OxmlElement(f"w:{border_name}")
        border_el.set(qn("w:val"), "single")
        border_el.set(qn("w:sz"), "8")
        border_el.set(qn("w:space"), "0")
        border_el.set(qn("w:color"), "000000")
        tblBorders.append(border_el)
    tbl.tblPr.append(tblBorders)


def _records_from_pdf_bytes(pdf_bytes: bytes) -> List[Dict]:
    """Upload the uploaded PDF (bytes) to Gemini and get a list of records.
    Mirrors process in index2-word_converter.py but works on uploaded file only.
    """
    load_api_key()
    model = genai.GenerativeModel(model_name=GEMINI_MODEL_NAME)

    # Write to a NamedTemporaryFile so genai.upload_file can read it
    with tempfile.NamedTemporaryFile(delete=True, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp.flush()
        pdf_path = pathlib.Path(tmp.name)
        pdf_file = genai.upload_file(path=pdf_path, display_name=pdf_path.name)
        prompt = get_multipage_extraction_prompt()
        response = model.generate_content([prompt, pdf_file])
        json_text = response.text.strip().replace("```json", "").replace("```", "")
        list_of_data = json.loads(json_text)
        if not isinstance(list_of_data, list):
            return []

    all_records = []
    for i, data in enumerate(list_of_data):
        area_sqm = clean_and_convert_to_float(data.get("area_sq_meter"))
        stamp_duty = clean_and_convert_to_float(data.get("stamp_duty"))
        amount = clean_and_convert_to_float(data.get("amount"))
        survey_norm = normalize_survey_numbers(data.get("survey_number"))

        hectares = area_sqm / 10000 if area_sqm > 0 else 0
        rate_per_sqm = amount / area_sqm if area_sqm > 0 else 0
        rate_per_guntha = rate_per_sqm * 100 if rate_per_sqm > 0 else 0
        rate_per_ha = rate_per_sqm * 10000 if rate_per_sqm > 0 else 0

        processed_data = {
            "dast_kramank_year": data.get("dast_kramank_year", "N/A"),
            "sub_registrar_number": data.get("sub_registrar_number", "N/A"),
            "dast_kramank_full": data.get("dast_kramank_full", "N/A"),
            "registration_date": data.get("registration_date", "N/A"),
            "document_type": data.get("document_type", "N/A"),
            "survey_number": survey_norm if survey_norm else "N/A",
            "area_sq_meter": f"{area_sqm:.4f}",
            "area_hectares": f"{hectares:.8f}",
            "stamp_duty": f"{stamp_duty:.2f}",
            "rate_per_sqm": f"{rate_per_sqm:.2f}",
            "rate_per_guntha": f"{rate_per_guntha:.2f}",
            "rate_per_ha": f"{rate_per_ha:.2f}",
            "prakar": data.get("prakar", "N/A"),
            "amount": f"{amount:.2f}",
            "page_record_num": i + 1,
        }
        all_records.append(processed_data)

    return all_records


def _build_base_table_docx(doc: Document, records: List[Dict]) -> Tuple[List[str], List[List[str]]]:
    """Append rows to template's first table from records. Returns (header, rows) for HTML rendering."""
    # Keep the template's original (Marathi) header labels intact for display
    # Column positions are assumed to match the order we append values below.

    table = doc.tables[0]
    rows_for_html: List[List[str]] = []
    serial_number = 1
    for rec in records:
        values = [
            str(serial_number),                      # 0 व्यवहार क्र. / Serial Number
            rec["dast_kramank_year"],               # 1 Year
            rec["sub_registrar_number"],            # 2 Sub Registrar Number
            rec["dast_kramank_full"],               # 3 Dast Kramank
            rec["registration_date"],               # 4 Registration Date (dd/mm/yyyy expected)
            rec["document_type"],                   # 5 Document Type
            rec["survey_number"],                   # 6 Survey Number
            rec["area_sq_meter"],                   # 7 Area (sq meters)
            rec["area_hectares"],                  # 8 Area (Hectares)
            rec["stamp_duty"],                      # 9 Stamp Duty
            rec["rate_per_sqm"],                    # 10 Rate per SqM
            rec["rate_per_guntha"],                 # 11 Rate per Guntha
            rec["rate_per_ha"],                     # 12 Rate per Ha
            rec.get("amount", ""),                  # 13 Amount
            ""                                      # 14 (Reserved for Shera)
        ]
        cells = table.add_row().cells
        for i, val in enumerate(values):
            str_val = str(val) if val is not None else ""
            if i < len(cells):
                cells[i].text = str_val
            values[i] = str_val
        rows_for_html.append(values)
        serial_number += 1

    add_table_borders(table)
    # Read the visual header texts from the template's header row (row index 1)
    try:
        visual_header = [cell.text.strip() for cell in table.rows[1].cells]
    except Exception:
        # Fallback: derive empty headers of same length
        visual_header = [""] * len(table.rows[0].cells)
    return visual_header, rows_for_html


def _to_float(s: str) -> float:
    s_clean = re.sub(r"[^0-9.]", "", s or "")
    try:
        return float(s_clean) if s_clean else 0.0
    except ValueError:
        return 0.0


def _date_in_range(s: str, start_dt: datetime, end_dt: datetime) -> bool:
    try:
        dt = datetime.strptime((s or '').strip(), "%d/%m/%Y")
        return (dt >= start_dt) and (dt <= end_dt)
    except Exception:
        return False


def _build_followup_tables(doc: Document, visual_header: List[str], selected_rows: List[List[str]], start_dt: Optional[datetime] = None, end_dt: Optional[datetime] = None) -> Dict[str, List[List[str]]]:
    """Build the follow-up tables from user-selected rows.
    The manual prakar filter has already been applied (user selected rows via checkboxes).
    This function applies the date filter, then sorts, takes top 50%, and averages.
    Returns dict with keys: filtered_table, derived_table, top_table, avg_paragraph.
    """
    # Column index mapping using the same kept_headers definition
    idx_serial = 0
    idx_year = 1
    idx_subreg = 2
    idx_dast = 3
    idx_reg_date = 4
    idx_doc_type = 5
    idx_survey = 6
    idx_area_sqm = 7
    idx_area_ha = 8
    idx_stamp = 9
    idx_rate_sqm = 10
    idx_rate_guntha = 11
    idx_rate_ha = 12
    idx_amount = 13
    idx_shera = 14

    # Start with user-selected rows (prakar filter already applied manually)
    filtered = list(selected_rows)

    # Apply date range filter if provided by caller
    if start_dt and end_dt:
        filtered_in_range = []
        for r in filtered:
            if _date_in_range(r[idx_reg_date], start_dt, end_dt):
                filtered_in_range.append(r)
        filtered = filtered_in_range

    # Sort by '(11) Rate per SqM' desc and keep top 50% (round up)
    filtered.sort(key=lambda r: _to_float(r[idx_rate_sqm]), reverse=True)
    n = len(filtered)
    keep_n = max(1, math.ceil(n * 0.5)) if n > 0 else 0
    top_half = filtered[:keep_n]

    # Insert a heading and a new table for filtered rows (Second table)
    doc.add_paragraph("फिल्टर केलेले")
    new_table = doc.add_table(rows=1, cols=len(visual_header))
    new_table.style = doc.tables[0].style
    for c_idx, text in enumerate(visual_header):
        new_table.rows[0].cells[c_idx].text = text

    for r in filtered:
        cells = new_table.add_row().cells
        for c_idx, text in enumerate(r[:len(visual_header)]):
            cells[c_idx].text = text
    add_table_borders(new_table)

    # Build derived table with selected columns + computed 'दर प्रती चौ.मी.'
    derived_indices = [
        idx_serial,    # Transaction / Serial No.
        idx_survey,    # Survey Number
        idx_area_sqm,  # Area (sq meters)
        idx_area_ha,   # Area (Hectares)
        idx_dast,      # Dast Kramank
        idx_reg_date,  # Registration Date
        idx_amount,    # Amount
        idx_doc_type   # Document Type
    ]

    doc.add_paragraph("निवडक स्तंभ व नवीन 'दर प्रती चौ.मी.' सह")
    derived_header = [visual_header[i] for i in derived_indices] + ["दर प्रती चौ.मी."]
    derived_table = doc.add_table(rows=1, cols=len(derived_header))
    derived_table.style = doc.tables[0].style
    for c_idx, text in enumerate(derived_header):
        derived_table.rows[0].cells[c_idx].text = text

    def compute_rate(row):
        amt = _to_float(row[idx_amount]) if len(row) > idx_amount else 0.0
        area = _to_float(row[idx_area_sqm]) if len(row) > idx_area_sqm else 0.0
        return (amt / area) if area > 0 else 0.0

    derived_rows = []
    for r in filtered:
        rate = compute_rate(r)
        values = [r[i] if i < len(r) else "" for i in derived_indices]
        cells = derived_table.add_row().cells
        for c_idx, text in enumerate(values + [f"{rate:.2f}"]):
            cells[c_idx].text = text
        derived_rows.append((values, rate))
    add_table_borders(derived_table)

    # Third: top 50% of derived by new rate
    derived_rows.sort(key=lambda t: t[1], reverse=True)
    n2 = len(derived_rows)
    keep_n2 = max(1, math.ceil(n2 * 0.5)) if n2 > 0 else 0
    top_half_rows = derived_rows[:keep_n2]

    doc.add_paragraph("टॉप 50% (नवीन 'दर प्रती चौ.मी.' नुसार)")
    top_header = derived_header
    top_table = doc.add_table(rows=1, cols=len(top_header))
    top_table.style = doc.tables[0].style
    for c_idx, text in enumerate(top_header):
        top_table.rows[0].cells[c_idx].text = text
    for values, rate in top_half_rows:
        cells = top_table.add_row().cells
        for c_idx, text in enumerate(values + [f"{rate:.2f}"]):
            cells[c_idx].text = text
    add_table_borders(top_table)

    # Average
    avg_value = (sum(rate for _, rate in top_half_rows) / len(top_half_rows)) if top_half_rows else 0.0
    avg_paragraph = f"Average दर प्रती चौ.मी. = {avg_value:.2f}"
    doc.add_paragraph(avg_paragraph)

    # Prepare structures for HTML rendering
    def table_to_rows(t):
        return [[cell.text for cell in row.cells] for row in t.rows]

    return {
        "filtered_table": table_to_rows(new_table),
        "derived_table": table_to_rows(derived_table),
        "top_table": table_to_rows(top_table),
        "avg_paragraph": avg_paragraph,
    }


def _render_table_html(rows: List[List[str]]) -> str:
    """Render a list-of-lists table into an HTML <table class='data'>."""
    if not rows:
        return ""
    head_html = "<thead><tr>" + "".join(f"<th>{pd.isna(h) and '' or h}</th>" for h in rows[0]) + "</tr></thead>"
    body_rows = rows[1:] if len(rows) > 1 else []
    body_html = "<tbody>" + "".join(
        "<tr>" + "".join(f"<td>{pd.isna(c) and '' or c}</td>" for c in r) + "</tr>" for r in body_rows
    ) + "</tbody>"
    return f"<table class=\"data\">{head_html}{body_html}</table>"


def _render_checkbox_table_html(header: List[str], rows: List[List[str]]) -> str:
    """Render a table with a checkbox column for user selection.
    Each row gets a checkbox; the first column (serial number) is used as value.
    """
    if not rows:
        return "<p>No records to display.</p>"
    # Header with checkbox column
    head_html = "<thead><tr><th>Select</th>" + "".join(f"<th>{pd.isna(h) and '' or h}</th>" for h in header) + "</tr></thead>"
    # Body rows with checkboxes
    options = [
        "",
        "बिनशेती स्वरूपाचा व्यवहार",
        "सदनिकेचा व्यवहार",
        "शून्य दरचा व्यवहार",
        "वाजवी दरापेक्षा कमी दराचा व्यवहार",
        "वाजवी दरापेक्षा जास्त दराचा व्यवहार",
        "शासकीय स्वरूपाचा व्यवहार",
        "बांधकामासहीत केलेला व्यवहार"
    ]
    opts_html = "".join(f'<option value="{opt}">{opt}</option>' for opt in options)

    body_parts = []
    for idx, r in enumerate(rows):
        checkbox = f'<input type="checkbox" class="prakar-row-checkbox" data-row-index="{idx}" checked onchange="document.getElementById(\'shera-dropdown-{idx}\').disabled = this.checked; document.getElementById(\'shera-star-{idx}\').style.display = this.checked ? \'none\' : \'inline\';">'
        cells_html = ""
        for c_idx, c in enumerate(r):
            if c_idx == 14:
                # generate dropdown for Shera
                cells_html += f'<td><select class="shera-dropdown" id="shera-dropdown-{idx}" disabled>{opts_html}</select><span id="shera-star-{idx}" style="color:red; display:none; margin-left:4px; font-weight:bold;">*</span></td>'
            else:
                cells_html += f"<td>{pd.isna(c) and '' or c}</td>"
        body_parts.append(f"<tr><td style='text-align:center'>{checkbox}</td>{cells_html}</tr>")
    body_html = "<tbody>" + "".join(body_parts) + "</tbody>"
    return f"<table class=\"data\">{head_html}{body_html}</table>"


def _render_followup_tables_as_html(followup: Dict[str, List[List[str]]]) -> str:
    """Render the follow-up tables (after manual selection) into HTML."""
    html_parts = []

    html_parts.append("<h3>फिल्टर केलेले</h3>")
    html_parts.append(_render_table_html(followup.get("filtered_table", [])))

    html_parts.append("<h3>निवडक स्तंभ व नवीन 'दर प्रती चौ.मी.' सह</h3>")
    html_parts.append(_render_table_html(followup.get("derived_table", [])))

    html_parts.append("<h3>टॉप 50% (नवीन 'दर प्रती चौ.मी.' नुसार)</h3>")
    html_parts.append(_render_table_html(followup.get("top_table", [])))

    html_parts.append(f"<p><strong>{followup.get('avg_paragraph','')}</strong></p>")
    return "\n".join(html_parts)


def process_index2_pdf_step1(pdf_bytes: bytes) -> Tuple[str, List[str], List[List[str]]]:
    """Step 1: Extract records from PDF and build the base table + checkbox table HTML.
    Returns (step1_html, base_header, base_rows).
    The step1_html includes the base table and a checkbox table for manual prakar filtering.
    """
    # Extract records
    records = _records_from_pdf_bytes(pdf_bytes)

    # Prepare docx in memory (for structure & styling parity)
    doc = Document(WORD_TEMPLATE_FILE)

    # Base table
    base_header, base_rows = _build_base_table_docx(doc, records)

    # Build step 1 HTML: base table + instruction + checkbox table
    base_rows_all = [base_header] + base_rows
    html_parts = []
    html_parts.append("<h3>Index-II Extracted Records</h3>")
    html_parts.append(_render_table_html(base_rows_all))

    # Instruction and checkbox table for manual prakar selection
    html_parts.append("<h3>प्रकार फिल्टर (Prakar Filter)</h3>")
    html_parts.append("<p>Check the boxes of the rows you want to keep and then click Proceed. "
                      "(जे रो ठेवायचे आहेत त्यांच्या बॉक्सेस तपासा आणि पुढे जा बटण दाबा.)</p>")
    html_parts.append('<div id="prakarCheckboxTable">')
    html_parts.append(_render_checkbox_table_html(base_header, base_rows))
    html_parts.append('</div>')
    html_parts.append('<button type="button" id="prakarProceedBtn" onclick="submitPrakarSelection()" '
                      'style="background-color:#28a745;color:white;border:none;padding:10px 20px;'
                      'border-radius:5px;cursor:pointer;margin-top:10px;">'
                      'Proceed (पुढे जा)</button>')

    step1_html = "\n".join(html_parts)
    return step1_html, base_header, base_rows


def process_index2_pdf_step2(base_header: List[str], base_rows: List[List[str]],
                              selected_indices: List[int],
                              shera_values: Dict[str, str],
                              base_date_str: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Step 2: Apply the remaining pipeline to user-selected rows.
    Returns (final_html, tmp_docx_path).
    """
    # Get the selected rows and update Shera column for all rows
    selected_rows = []
    for i, r in enumerate(base_rows):
        if i in selected_indices:
            r[14] = "स्वीकृत व्यवहार"
            selected_rows.append(r)
        else:
            val = shera_values.get(str(i), "")
            r[14] = val if val else "कारण दिले नाही"

    # Compute date range from provided base date string
    start_dt = None
    end_dt = None
    if base_date_str:
        try:
            base_dt = datetime.strptime(base_date_str.strip(), "%Y-%m-%d")
            start_dt = datetime(base_dt.year - 3, base_dt.month, base_dt.day)
            end_dt = datetime(base_dt.year, base_dt.month, base_dt.day)
        except Exception:
            start_dt = None
            end_dt = None

    # Build docx for the follow-up tables
    doc = Document(WORD_TEMPLATE_FILE)
    # Re-add the base table into the docx for completeness
    table = doc.tables[0]
    for r in base_rows:
        cells = table.add_row().cells
        for i, val in enumerate(r):
            if i < len(cells):
                cells[i].text = str(val) if val is not None else ""
    add_table_borders(table)

    # Follow-up tables with selected rows and optional date range
    followup = _build_followup_tables(doc, visual_header=base_header,
                                       selected_rows=selected_rows,
                                       start_dt=start_dt, end_dt=end_dt)

    # Render follow-up tables to HTML
    html = _render_followup_tables_as_html(followup)

    # Save DOCX to temp for download
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.docx') as tmp_doc:
            doc.save(tmp_doc.name)
            tmp_path = tmp_doc.name
    except Exception:
        tmp_path = None

    return html, tmp_path
