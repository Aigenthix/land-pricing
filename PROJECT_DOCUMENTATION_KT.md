# Land Pricing Tool (जमीन किंमत साधन) — Comprehensive Knowledge Transfer (KT) & Architecture Guide

**Client / Stakeholder:** Divisional Commissioner — Konkan Division, Government of Maharashtra (GoM)  
**Research & Development:** Center for Research and Development, Vijaybhoomi University / AiGENThix  
**Target Audience:** Software Engineers, Interns, and Technical Contributors taking over this codebase.

---

## 1. Executive Summary & Business Domain

### 1.1 Purpose of the Tool
Under the Indian Land Acquisition Act (*Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act, 2013 - RFCTLARR Act*, specifically Section 26), determining the fair compensation for land acquired for public infrastructure projects requires assessing:
1. **Sales Statistics / Precedent Transactions:** Average price of recorded sales transactions of similar lands in the vicinity over the preceding 3 years (extracted from Sub-Registrar **Index-II** documents).
2. **Ready Reckoner (ASR) Rates:** State Government official market valuation rates published on the **IGR Maharashtra** (Inspector General of Registration and Controller of Stamps) eASR portal.
3. **Final Compensation Rule:** The law generally mandates taking the **higher** of the two rates, subject to statutory regional adjustments (e.g., depreciation for public purpose/bulk/undulated land and appreciation for TDR in Mumbai/Mumbai-Suburban).

Before this tool, revenue officers, deputy collectors, and consultants manually processed hundreds of scanned Marathi Index-II records and navigated clunky government portals—a process taking days per village. This application automates the entire pipeline into an AI-assisted, human-in-the-loop web platform.

---

## 2. High-Level Architecture

The system consists of a Flask web backend, browser-based UI, external LLM OCR service (Google Gemini), local computer vision OCR (DocTR), and headless browser scraping (Playwright).

```
                      +---------------------------------------+
                      |          Web Browser (UI)             |
                      |   (templates/index.html, login.html)  |
                      +-------------------+-------------------+
                                          |
                        HTTP / AJAX Calls | Sessions & Auth
                                          v
                      +---------------------------------------+
                      |         Flask Server (main.py)        |
                      +-------+-------------------+-------+---+
                              |                   |       |
              +---------------+                   |       +----------------+
              v                                   v                        v
     [Tab 1: Method 1]                   [Tab 2: Method 2]         [Tab 3: Recommendation]
Sales Statistics / Index-II            IGR Ready Reckoner           Comparative Engine &
---------------------------          ----------------------         Regional Adjustments
• NEWmethod1.py (Gemini 2.5 Pro)     • NEWmethod2.py (Playwright)   • Evaluates Max(M1, M2)
• Legacy: method1.py (SQLite)        • Legacy: method2.py (DocTR)   • Mumbai TDR / Depr.
• Generates styled DOCX              • Section 11 DOCX parsing      • Output: Rs/sqm & Rs/Ha
```

---

## 3. Deep Dive: Method 1 (Sales Statistics / Index-II Analysis)

### 3.1 What is "Index-II" (सूची क्र. २)?
When property transactions are registered in Maharashtra, the Sub-Registrar Office issues an "Index-II" document summarizing:
- **दस्त क्रमांक (Dast Kramank):** Registration Deed Number & Year
- **नोंदणी दिनांक (Registration Date):** Date deed was registered
- **विलेखाचा प्रकार (Document Type):** Deed of Sale, Conveyance, Gift, Mortgage, etc.
- **भूमापन क्रमांक (Survey / Gut Number):** Land parcel numbers
- **क्षेत्रफळ (Area):** In Sq. Meters, Sq. Feet, or Hectares
- **मोबदला (Consideration Amount):** Transaction sale value in INR
- **मुद्रांक शुल्क (Stamp Duty):** Market value stamp duty paid

---

### 3.2 Old Method 1 (`method1.py`)
- **How it worked:**
  - Depended on a human first transcribing Index-II documents into a Microsoft Word (`.docx`) table.
  - Read the `.docx` table using `python-docx` into a pandas DataFrame.
  - Pushed the DataFrame into an in-memory SQLite database (`sqlite:///:memory:`).
  - Executed hardcoded SQL queries:
    ```sql
    -- Date range filter
    SELECT * FROM mytable WHERE `दिनांक` BETWEEN '2020-05-02' AND '2023-05-02';
    -- Filter zero/near-zero values
    SELECT * FROM ... WHERE `खरेदी किंमत` NOT IN (0, 1) AND `प्रती चौ.मी.` NOT BETWEEN 0 AND 10;
    -- Exclude non-sale deed types
    SELECT * FROM ... WHERE `दस्ताचा प्रकार` NOT IN ('कन्व्हेन्स डीड', '65-चुक दुरुस्ती पत्र', 'करारनामा');
    ```
  - Excluded survey numbers passed as a comma-separated string.
  - Filtered out `अभिहस्तांतरणपत्र` where consideration != 600,000.
  - Sorted remaining transactions descending by `प्रती चौ.मी.` and selected the top 50% (`top_half_df`).
  - Calculated arithmetic average of top 50%.
- **Drawbacks of Old Method:**
  - Did NOT perform OCR: required manual data entry into Word.
  - Hardcoded dates and transaction types.
  - Brittle and inflexible for non-standard formats.

---

### 3.3 New Method 1 (`NEWmethod1.py` & `index2-word_converter.py`)
- **Architecture:** Directly reads multi-page scanned Marathi PDF documents using Google Gemini Vision API (`models/gemini-2.5-pro`).
- **Pipeline Workflow:**

```
  [Uploaded Marathi PDF]
            |
            v
  [Gemini 2.5 Pro Vision OCR] ---> Ignores receipt/payment pages
            |                  ---> Extracts JSON array of Index-II records
            v
  [Normalization & Unit Conversion]
  • Sq. Ft -> Sq. M (* 0.092903)
  • Hectares -> Sq. M (* 10,000)
  • Rate/sq.m = Amount / Area_sqm
            |
            v
  [Step 1: UI Base Table + Interactive Prakar Filter]
  • Renders base extracted table
  • Interactive checkboxes for each row
  • Mandatory Marathi reason (शेरा / Shera) dropdown for unselected rows
            |
            v
  [Step 2: Backend Filter & Aggregation]
  • Date Filter: Automatic 3-year lookback from user's Base Date
  • Leaner Derived Table: Sorted descending by Rate/sq.m
  • Top 50% Selection
  • Average Rate per Sq. Meter
            |
            v
  [DOCX Exporter] (index2/format.docx) -> Downloadable Official Word Report
```

- **Allowed Marathi Shera (Reasons for Rejection):**
  1. `बिनशेती स्वरूपाचा व्यवहार` (Non-agricultural transaction)
  2. `सदनिकेचा व्यवहार` (Flat/apartment transaction)
  3. `शून्य दरचा व्यवहार` (Zero-rate transaction)
  4. `वाजवी दरापेक्षा कमी दराचा व्यवहार` (Abnormally low price transaction)
  5. `वाजवी दरापेक्षा जास्त दराचा व्यवहार` (Abnormally high price transaction)
  6. `शासकीय स्वरूपाचा व्यवहार` (Government institutional transaction)
  7. `बांधकामासहीत केलेला व्यवहार` (Transaction including structures/buildings)

---

## 4. Deep Dive: Method 2 (IGR Ready Reckoner / eASR Web Scraping)

### 4.1 What is IGR eASR?
The Maharashtra Government's **eASR 2.0 (e-Annual Statement of Rates)** portal (`igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx`) provides the statutory benchmark rates for land valuation across Districts, Talukas, and Villages.

---

### 4.2 Old Method 2 (`method2.py`, `Fin_plsplspls.py`, `igr_scraper.py`)
- **How it worked:**
  - Depended on an image upload of a **7/12 land record (सातबारा उतारा)**.
  - Ran local PyTorch + DocTR OCR (`RobustLandRecordOCRDocTR`) on the image crop (`y: 20-55%`, `x: 0-20%`).
  - Extracted two fields: **Assessment (आकारणी)** and **Total Cultivable Area (एकूण लागवडीयोग्य क्षेत्र)**.
  - Calculated:
    $$\text{Assessment Value} = \frac{\text{Assessment}}{\text{Total Cultivable Area}}$$
  - Navigated to eASR via Playwright, selected Year, Taluka, and Village.
  - Scraped the rural assessment rate table (`#ctl00_ContentPlaceHolder5_ruralDataGrid`).
  - Looked for the slab matching the calculated assessment value (e.g. `1.26 - 2.50`) and read the rate in Rs./Hectare.
- **Drawbacks of Old Method:**
  - DocTR model is heavyweight (~2GB dependencies: PyTorch, Torchvision, OpenCV).
  - High error rate on degraded, handwritten, or low-resolution 7/12 scans.
  - Only worked for rural agricultural slabs; **completely failed for urban/semi-urban zones** with multiple valuation subzones.

---

### 4.3 New Method 2 (`NEWmethod2.py`)
- **How it works:**
  - Ingests the **Section 11 Land Acquisition Notification (`.docx`)** directly.
  - **Document Entity Extraction:**
    - Paragraph scanning extracts District (`जिल्हा`), Taluka (`तालुका`), and Village (`मौजे`).
    - Table scanning locates column `भूमापन क्रमांक / गट क्रमांक` (Survey/Gut Number).
    - Normalizes complex survey numbers (e.g., `123/A` $\to$ `123A`, `123/3` $\to$ `123`, `123/इ` $\to$ `123इ`).
  - **Automated Playwright Navigation:**
    1. Opens eASR URL: `.../eASRCommon.aspx?hDistName=<District>`.
    2. Selects Year (e.g., `2023-2024`), Taluka, and Village.
    3. Handles English vs Marathi dropdown options (with `deep-translator` fallback).
    4. Switches to the **SubZones** valuation grid (`#ctl00_ContentPlaceHolder5_dg_Valuation2_0`).
  - **SubZone Survey Number Matching:**
    - For every row across paginated subzone tables, clicks the `SurveyNo` link.
    - An ASP.NET update panel loads a `<textarea>` containing all survey numbers included in that subzone.
    - Validates whether **ALL survey numbers** required in the Section 11 Notification are present in this subzone!
    - Upon match, extracts the exact Ready Reckoner Rate from Column 3.
  - **Fault Tolerance & Resilience:**
    - Detects and handles sudden portal redirects to `frmMap.aspx` (a common ASP.NET session glitch) by re-initiating the flow.
    - Safe pagination tracking via DOM text change and row signatures.

---

## 5. Method 3: Comparative Recommendation & Regional Adjustments

Implemented in `templates/index.html` (`compareRates()` function):

### 5.1 Base Comparison
$$\text{Base Recommended Rate} = \max(\text{Method 1 Rate}, \text{Method 2 Rate})$$
If only one method is executed, that method's rate is used.

### 5.2 Mumbai & Mumbai-Suburban Adjustments
When the user toggles the Mumbai/Mumbai-Suburban region checkbox:

1. **Depreciation (Compounded deduction on base rate):**
   - Land reserved for Public Purpose: $-20\%$
   - Bulk Land: $-15\%$
   - Undulated / Underdeveloped Land: $-X\%$ (user input percentage)
   $$\text{Total Depreciation \%} = 20\% + 15\% + X\%$$
   $$\text{Rate after Depreciation} = \text{Base Rate} \times \left(1 - \frac{\text{Total Depreciation \%}}{100}\right)$$

2. **Appreciation (TDR - Transferable Development Rights):**
   - Mumbai City: $+25\%$
   - Mumbai Sub-urban: $+40\%$
   $$\text{Final Adjusted Rate (per sq.m)} = \text{Rate after Depreciation} \times (1 + \text{TDR \%})$$

3. **Rate per Hectare Conversion:**
   $$\text{Rate per Hectare} = \text{Final Adjusted Rate per sq.m} \times 10,000$$

---

## 6. Repository Structure & File Catalog

| File / Folder | Role & Description |
|---|---|
| `main.py` | Primary Flask application. Routes for login, Tab 1, Tab 2, Tab 3, session management. |
| `NEWmethod1.py` | **Active Method 1:** Gemini 2.5 Pro OCR on Index-II PDFs, Prakar filter, date filter, DOCX generation. |
| `NEWmethod2.py` | **Active Method 2:** Word parser for Section 11 notifications, Playwright scraper for eASR subzones. |
| `method1.py` | **Legacy Method 1:** SQLite query-based filtering on pre-made Word tables. |
| `method2.py` / `igr_scraper.py` | **Legacy Method 2:** Playwright scraper for rural assessment grid. |
| `Fin_plsplspls.py` | **Legacy OCR:** PyTorch + DocTR local OCR for 7/12 land record images. |
| `index2-word_converter.py` | CLI precursor script for batch Index-II extraction using Gemini. |
| `csv-table-process.py` | Utility script converting CSV tables to styled DOCX. |
| `probe_igr_table.py` | Diagnostic script for inspecting IGR portal DOM selectors and frames. |
| `test_ocr.py` | Standalone verification test for DocTR 7/12 image OCR. |
| `templates/index.html` | Frontend UI containing the 3-tab layout, AJAX forms, spinners, and recommendation logic. |
| `templates/login.html` | Portal login page with official Government of Maharashtra and University logos. |
| `static/` | Government seals, logos (`konkan.jpg`, `symbol.jpg`, `gov_logo.jpg`, `vija.png`). |
| `index2/` | Reference datasets, format templates (`format.docx`), sample PDFs, and Section 11 docs. |
| `7_12 images/` | Sample 7/12 land record scans for testing DocTR OCR. |
| `dockerfile` & `render.yaml` | Production container configuration for deployment on Render. |
| `pyproject.toml` & `requirements.txt` | Python package specifications. |

---

## 7. Setup & Execution Guide

### 7.1 Prerequisites
- Python 3.10 or 3.11
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or standard `pip`

### 7.2 Installation
```bash
# 1. Create and sync virtual environment
uv venv
uv sync

# 2. Install Playwright browser binaries
source .venv/bin/activate       # On Linux/macOS
# or: .venv\Scripts\activate   # On Windows
playwright install
```

### 7.3 Configuration (`.env`)
Create a `.env` file in the root directory:
```env
GOOGLE_API_KEY=your_gemini_api_key_here
SECRET_KEY=optional_custom_flask_secret_key
```

### 7.4 Running the Application
```bash
# Using Gunicorn (Production)
gunicorn --workers 1 --threads 2 --bind 0.0.0.0:5001 --timeout 120 main:app

# Or for local development:
python main.py
```
- Open `http://localhost:5001`
- **Default Credentials:** Username: `admin` | Password: `5555`

---

## 8. Common Pitfalls & Maintenance Tips for Juniors

1. **Google Gemini Model Changes:**
   `NEWmethod1.py` uses `models/gemini-2.5-pro`. Ensure your Google Cloud Project has access to Gemini 2.x models and valid API quotas.
2. **eASR Portal Structural Updates:**
   The IGR Maharashtra portal (`igreval.maharashtra.gov.in`) uses legacy ASP.NET WebForms with `__doPostBack` and viewstate updates. If Government IT updates element IDs (like `ddlTaluka`, `dg_Valuation2_0`), update selectors in `NEWmethod2.py`.
3. **Headless vs Headed Playwright:**
   `NEWmethod2.py` sets `headless=False` by default in `process_igr_from_doc` so operators can observe the scraping. On headless cloud servers (e.g. Render/Docker), this must be set to `headless=True` (configured in Dockerfile via Xvfb or Chromium flags).
4. **Devanagari (Marathi) String Normalization:**
   Always use Unicode normalization (`unicodedata.normalize('NFKC', text)`) and strip zero-width characters (`\u200c`, non-breaking spaces `\u00a0`) when matching Marathi village names and survey numbers.
