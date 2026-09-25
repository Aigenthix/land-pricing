# land-pricing
*There is a lot of code files here, this is because I required two different methods and have kept them both in the same branch*

### 1. First, Install UV and install dependencies
```bash
uv venv
uv sync
```

### 2. Create a `.env` file in the /root directory of the format below and enter the Gemini API key
```
GOOGLE_API_KEY=''
SECRET_KEY=''  # optional
```
- Input your Google Gemini API key between the quotes

### 3. Install Playwright inside your venv
```bash
source .venv/bin/activate # linux/mac
# or .venv\Scripts\activate on Windows
playwright install
```

### 4. Run the application
```bash
gunicorn --workers 1 --threads 2 --bind 0.0.0.0:5001 --timeout 120 main:app
# Or for development: python main.py
```
- Runs on `http://localhost:5001`
- **Login Credentials:** Username: `admin` | Password: `5555`

## For DEMO
### 1. In Tab 1 (Index2 Analysis)
- Upload the PDF: `index2/files/majiwada_index2.pdf`
- Select a Base Date (e.g., `2024-03-31`)
- Click **Process Index-II** (Gemini extracts Index-II records)
- In the Prakar Filter table, review rows. Uncheck non-qualifying rows and select a Marathi Shera (reason)
- Click **Proceed** to view date-filtered, sorted top 50% records, and average rate (download DOCX if needed)

### 2. In Tab 2 (IGR Web Scraping)
- Upload the Section 11 Notification: `index2/11Notification-new-majivade-extended.docx`
- Select Year: `2023-2024`
- Enter District: `Thane`, Taluka: `Thane`, Village: `Majiwade`
- Click **Process**
- The scraper automates the IGR eASR portal, matches Survey Numbers against SubZones, and returns the rate

### 3. In Tab 3 (Recommendation)
- Select regional adjustment criteria (e.g., Mumbai/Mumbai-Suburban, Public Purpose, Bulk Land, TDR)
- Click **Get Recommended Rate** to compare Method 1 vs Method 2 and get the final compensation rate
