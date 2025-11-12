from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch Chromium (set headless=False if you want to see the browser)
    browser = p.chromium.launch(
        proxy={"server": "http://host:port", "username": "USER", "password": "PASS"},
        args=["--no-sandbox","--disable-dev-shm-usage"],
        headless=True
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 ... Chrome/120 Safari/537.36",
        locale="en-IN",
        extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"}
    )
    page = context.new_page()
    # Navigate to the URL
    page.goto("https://igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx?hDistName=Palghar")

    # Get the full page HTML
    html = page.content()
    print(html)

    browser.close()
