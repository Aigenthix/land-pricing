from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    # Launch Chromium (set headless=False if you want to see the browser)
    browser = p.chromium.launch(headless=false)
    page = browser.new_page()

    # Navigate to the URL
    page.goto("https://igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx?hDistName=Palghar")

    # Get the full page HTML
    html = page.content()
    print(html)

    browser.close()
