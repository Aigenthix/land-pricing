from playwright.sync_api import sync_playwright
import time
import re
from bs4 import BeautifulSoup

class IGRScraper:
    def __init__(self, headless=True):
        """Initialize the IGR scraper with Playwright"""
        self.base_url = 'https://igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx?hDistName='
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None
    
    def start_browser(self):
        """Start the browser session"""
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()
        
        # Set longer timeout for slow loading pages
        self.page.set_default_timeout(30000)
    
    def parse_rate_from_table(self, table_html, area_value):
        """Parse the table and find the rate for the given area value"""
        try:
            soup = BeautifulSoup(table_html, 'html.parser')
            table = soup.find('table', {'id': 'ctl00_ContentPlaceHolder5_ruralDataGrid'})
            
            if not table:
                print("Could not find the rate table")
                return None
            
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    assessment_range = cells[1].get_text().strip()
                    rate = cells[2].get_text().strip()
                    
                    # Parse the range (e.g., "1.26-2.50" or "0-1.25")
                    if self.is_value_in_range(area_value, assessment_range):
                        print(f"Area {area_value} falls in range: {assessment_range}")
                        print(f"Corresponding rate: Rs. {rate}")
                        return rate
            
            print(f"No matching range found for area value: {area_value}")
            return None
            
        except Exception as e:
            print(f"Error parsing table: {str(e)}")
            return None
    
    def is_value_in_range(self, value, range_str):
        """Check if a value falls within a given range string"""
        try:
            # Handle ranges like "0-1.25", "1.26-2.50", "12.51-च्या पुढे"
            if "पुढे" in range_str:  # "च्या पुढे" means "and above"
                # Extract the lower bound
                match = re.search(r'([0-9.]+)', range_str)
                if match:
                    lower_bound = float(match.group(1))
                    return value >= lower_bound
            else:
                # Regular range like "1.26-2.50"
                parts = range_str.split('-')
                if len(parts) == 2:
                    lower_bound = float(parts[0])
                    upper_bound = float(parts[1])
                    return lower_bound <= value <= upper_bound
            
            return False
        except:
            return False
    
    def scrape_data(self, district, year, taluka, village, area_value=None):
        """
        Scrape data for given district, year, taluka, and village
        
        Args:
            district (str): District name
            year (str): Year to select
            taluka (str): Taluka name
            village (str): Village name
            
        Returns:
            str: HTML content of the resulting table, or rate if area_value provided
        """
        try:
            if not self.page:
                self.start_browser()
            
            # Navigate to the website with district parameter
            url = f"{self.base_url}{district}"
            print(f"Navigating to: {url}")
            self.page.goto(url)
            
            # Wait for page to load
            self.page.wait_for_load_state('networkidle')
            
            # Select Year from dropdown
            print(f"Selecting year: {year}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlYear')
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlYear', label=year)
            time.sleep(2)
            
            # Select Taluka from dropdown
            print(f"Selecting taluka: {taluka}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlTaluka')
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlTaluka', label=taluka)
            time.sleep(2)
            
            # Select Village from dropdown
            print(f"Selecting village: {village}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlVillage')
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlVillage', label=village)
            time.sleep(3)
            
            # Wait for table to appear and extract HTML
            print("Waiting for table to load...")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ruralDataGrid', timeout=15000)
            
            # Get the HTML of the specific table
            table_html = self.page.locator('#ctl00_ContentPlaceHolder5_ruralDataGrid').inner_html()
            print("Table HTML extracted successfully!")
            
            full_table_html = f"<table id='ctl00_ContentPlaceHolder5_ruralDataGrid'>{table_html}</table>"
            
            # If area value is provided, find and print the corresponding rate
            if area_value is not None:
                rate = self.parse_rate_from_table(full_table_html, area_value)
                return rate
            
            return full_table_html
            
        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            # Take screenshot for debugging
            try:
                self.page.screenshot(path=f"error_screenshot_{district}_{taluka}_{village}.png")
                print(f"Screenshot saved for debugging")
            except:
                pass
            return None
    
    def close(self):
        """Close the browser and playwright"""
        if self.page:
            self.page.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

def main():
    """Main function to test the scraper"""
    
#! [district, year, taluka, village, area_value]
    test_data = [
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 0.5],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 2.2],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 4.9],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 10],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 12],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 13],
        ["Thane", "2024-2025", "Ambarnath", "Ambhe", 0],
    ]
    
    scraper = IGRScraper(headless=False)  # Set to True for headless mode
    
    try:
        for row in test_data:
            district, year, taluka, village, area_value = row
            print(f"Finding rate for area: {area_value}")
            
            # Get the rate directly
            rate = scraper.scrape_data(district, year, taluka, village, area_value)
            
            if not rate:
                print(f"Failed to scrape data for {district}-{taluka}-{village}")
                
    except Exception as e:
        print(f"Error in main execution: {str(e)}")
    
    finally:
        scraper.close()

if __name__ == "__main__":
    main()
