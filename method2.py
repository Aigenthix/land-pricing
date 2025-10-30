import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import re
import atexit

# Thread-local browser instances to avoid greenlet switching issues
import threading
_thread_local = threading.local()

def get_browser_instance():
    """Get or create thread-local browser instance"""
    if not hasattr(_thread_local, 'browser_instance'):
        print("Initializing browser for current thread...")
        try:
            playwright = sync_playwright().start()
            browser = playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu', '--disable-extensions']
            )
            _thread_local.browser_instance = {
                'playwright': playwright,
                'browser': browser
            }
            print("Browser initialization complete for thread!")
        except Exception as e:
            print(f"Failed to initialize browser: {e}")
            _thread_local.browser_instance = None
    
    return _thread_local.browser_instance

class IGRScraper:
    def __init__(self, headless=True):
        """Initialize the IGR scraper with Playwright"""
        self.base_url = 'https://igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx?hDistName='
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.page = None
    
    def start_browser(self):
        """Start the browser session using thread-local instance"""
        browser_instance = get_browser_instance()
        
        if browser_instance is not None:
            print("Using thread-local browser instance...")
            self.playwright = browser_instance['playwright']
            self.browser = browser_instance['browser']
            
            # Always create a new page for each scraping session
            self.page = self.browser.new_page()
            
            # Set reasonable timeout for dynamic content
            self.page.set_default_timeout(20000)
        else:
            raise Exception("Failed to initialize browser")
    
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
                        return rate
            
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
    
    def scrape_data(self, district, year, taluka, village, area_value):
        """
        Scrape data for given district, year, taluka, village and area value
        
        Returns:
            dict: Contains rate_hectares, rate_sqm, and range info
        """
        try:
            if not self.page:
                self.start_browser()
            
            # Navigate to the website with district parameter
            url = f"{self.base_url}{district}"
            print(f"Navigating to: {url}")
            self.page.goto(url, wait_until='domcontentloaded')
            
            # Select Year from dropdown
            print(f"Selecting year: {year}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlYear', timeout=15000)
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlYear', label=year)
            time.sleep(2)
            self.page.wait_for_load_state('networkidle')
            
            # Select Taluka from dropdown
            print(f"Selecting taluka: {taluka}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlTaluka', timeout=15000)
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlTaluka', label=taluka)
            
            # Wait for village dropdown to populate after taluka selection
            time.sleep(3)
            self.page.wait_for_load_state('networkidle')
            
            # Select Village from dropdown
            print(f"Selecting village: {village}")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlVillage', timeout=15000)
            
            # Wait for village options to be available
            self.page.wait_for_function(
                "document.querySelector('#ctl00_ContentPlaceHolder5_ddlVillage').options.length > 1",
                timeout=10000
            )
            
            self.page.select_option('#ctl00_ContentPlaceHolder5_ddlVillage', label=village)
            time.sleep(2)
            self.page.wait_for_load_state('networkidle')
            
            # Wait for table to appear and extract HTML
            print("Waiting for table to load...")
            self.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ruralDataGrid', timeout=15000)
            
            # Get the HTML of the specific table
            table_html = self.page.locator('#ctl00_ContentPlaceHolder5_ruralDataGrid').inner_html()
            print("Table HTML extracted successfully!")
            
            full_table_html = f"<table id='ctl00_ContentPlaceHolder5_ruralDataGrid'>{table_html}</table>"
            
            # Parse the table to find matching rate
            soup = BeautifulSoup(full_table_html, 'html.parser')
            table = soup.find('table', {'id': 'ctl00_ContentPlaceHolder5_ruralDataGrid'})
            
            if not table:
                return {"error": "Could not find the rate table"}
            
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    assessment_range = cells[1].get_text().strip()
                    rate_hectares = cells[2].get_text().strip()
                    
                    # Parse the range and check if area_value fits
                    if self.is_value_in_range(area_value, assessment_range):
                        # Convert rate from hectares to square meters
                        # 1 hectare = 10,000 square meters
                        try:
                            rate_per_hectare = float(rate_hectares)
                            rate_per_sqm = rate_per_hectare / 10000
                            
                            return {
                                "range": assessment_range,
                                "rate_hectares": rate_per_hectare,
                                "rate_sqm": rate_per_sqm,
                                "area_value": area_value
                            }
                        except ValueError:
                            return {"error": f"Could not convert rate to number: {rate_hectares}"}
            
            return {"error": f"No matching range found for area value: {area_value}"}
            
        except Exception as e:
            print(f"Error during scraping: {str(e)}")
            return {"error": str(e)}
    
    def close_browser(self):
        """Close only the page, keep browser running"""
        if self.page:
            self.page.close()
            self.page = None
    

def get_land_rate(district, year, taluka, village, area_value):
    """
    Main function to get land rate using IGR scraper
    
    Returns:
        dict: Contains rate information or error
    """
    scraper = IGRScraper(headless=True)
    
    try:
        result = scraper.scrape_data(district, year, taluka, village, area_value)
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        scraper.close_browser()
