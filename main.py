from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import os
from dotenv import load_dotenv
from method1 import process_data
from method2 import get_land_rate
import threading
import time
import tempfile
from Fin_plsplspls import RobustLandRecordOCRDocTR
from NEWmethod1 import process_index2_pdf_to_html

load_dotenv()

# Global variable to store latest value from external sources
latest_value = {"val": None}

# Global variable to track processing status
processing_status = {"image_processing": False, "scraping_progress": {}, "index2_progress": {"step": 0, "message": "Not started"}}

# Initialize OCR processor globally
ocr_processor = None

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

def initialize_ocr():
    """Initialize OCR processor on first use"""
    global ocr_processor
    if ocr_processor is None:
        print("Initializing OCR processor...")
        ocr_processor = RobustLandRecordOCRDocTR()
        print("OCR processor initialized successfully!")
    return ocr_processor

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login_post():
    user_id = request.form['user_id']
    password = request.form['password']
    if user_id == 'admin' and password == '5555':
        session['logged_in'] = True
        return redirect(url_for('index'))
    return render_template('login.html', error='Invalid credentials')

@app.route('/index')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get all results from session to display them
    result_en = session.get('method1_result_en', None)
    result_mr = session.get('method1_result_mr', None)
    table = session.get('method1_table', None)
    method2_result = session.get('method2_result', None)
    method2_error = session.get('method2_error', None)
    
    return render_template('index.html', 
                         result_en=result_en, 
                         result_mr=result_mr, 
                         table=table,
                         method2_result=method2_result, 
                         method2_error=method2_error)

@app.route('/clear_results')
def clear_results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Clear all method results from session
    session.pop('method1_result_en', None)
    session.pop('method1_result_mr', None)
    session.pop('method1_table', None)
    session.pop('method1_index2_html', None)
    session.pop('method2_result', None)
    session.pop('method2_error', None)
    
    return redirect(url_for('index'))

@app.route('/process', methods=['POST'])
def process():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    docx_file = request.files['input_file']
    excluded_survey_numbers = request.form['excluded_survey_numbers']
    result_en, result_mr, table = process_data(docx_file.read(), excluded_survey_numbers)
    
    # Store results in session to prevent form resubmission
    session['method1_result_en'] = result_en
    session['method1_result_mr'] = result_mr
    session['method1_table'] = table.to_html(classes='data', header=True)
    
    return jsonify({
        "status": "success",
        "result_en": result_en,
        "result_mr": result_mr,
        "table": table.to_html(classes='data', header=True)
    })

@app.route('/process_index2', methods=['POST'])
def process_index2():
    """New Method 1 (Index2 Analysis): accepts a PDF, processes it via Gemini, and returns styled HTML tables.
    Does not write CSV or Word; renders HTML preserving styling classes.
    """
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401

    if 'input_file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    pdf_file = request.files['input_file']
    if not pdf_file or pdf_file.filename == '':
        return jsonify({"status": "error", "message": "No file uploaded"}), 400

    # Validate file type (pdf)
    if not pdf_file.filename.lower().endswith('.pdf'):
        return jsonify({"status": "error", "message": "Only PDF files are allowed"}), 400

    try:
        # Step 1: Detecting values using OCR (Gemini extract)
        processing_status["index2_progress"] = {"step": 1, "message": "Detecting values using OCR"}
        pdf_bytes = pdf_file.read()
        html, tmp_docx_path = process_index2_pdf_to_html(pdf_bytes)

        # Step 2: Filtering relevant details (done inside NEWmethod1)
        processing_status["index2_progress"] = {"step": 2, "message": "Filtering relevant details"}

        # Step 3: Calculating Land Price (rates and averages)
        processing_status["index2_progress"] = {"step": 3, "message": "Calculating Land Price"}

        # Store results
        session['method1_index2_html'] = html
        session['method1_index2_docx_path'] = tmp_docx_path

        # Step 4: Done
        processing_status["index2_progress"] = {"step": 4, "message": "Done"}

        return jsonify({"status": "success", "html": html, "download": bool(tmp_docx_path)})
    except Exception as e:
        processing_status["index2_progress"] = {"step": 0, "message": f"Error: {str(e)}"}
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get_index2_progress')
def get_index2_progress():
    return jsonify(processing_status.get("index2_progress", {"step": 0, "message": "Not started"}))

@app.route('/download_index2_docx')
def download_index2_docx():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    path = session.get('method1_index2_docx_path')
    if not path or not os.path.exists(path):
        return jsonify({"status": "error", "message": "No generated document available"}), 404
    # Use a friendly filename
    return send_file(path, as_attachment=True, download_name='index2_output.docx')

@app.route('/index_method1_results')
def index_with_method1_results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get Method 1 results
    result_en = session.get('method1_result_en', None)
    result_mr = session.get('method1_result_mr', None)
    table = session.get('method1_table', None)
    
    # Also get Method 2 results if they exist
    method2_result = session.get('method2_result', None)
    method2_error = session.get('method2_error', None)
    
    return render_template('index.html', 
                         result_en=result_en, 
                         result_mr=result_mr, 
                         table=table,
                         method2_result=method2_result, 
                         method2_error=method2_error)

@app.route('/check_processing_status')
def check_processing_status():
    """Check if image is still being processed"""
    return jsonify({"image_processing": processing_status["image_processing"]})

@app.route('/get_scraping_progress')
def get_scraping_progress():
    """Get real-time scraping progress"""
    # If there's any active session, return its progress (for single-user scenario)
    if processing_status["scraping_progress"]:
        # Get the most recent session (last one in the dict)
        session_id = list(processing_status["scraping_progress"].keys())[-1]
        progress = processing_status["scraping_progress"][session_id]
        print(f"[PROGRESS] Active session {session_id}: Step {progress['step']} - {progress['message']}")
        return jsonify(progress)
    
    print(f"[PROGRESS] No active sessions found")
    return jsonify({"step": 0, "message": "Not started"})

@app.route('/process_method2', methods=['POST'])
def process_method2():
    if not session.get('logged_in'):
        return jsonify({"status": "error", "message": "Not logged in"}), 401
    
    # Check if image is still being processed
    if processing_status["image_processing"]:
        return jsonify({"status": "error", "message": "Image is still being processed. Please wait for the assessment value to be detected."}), 400
    
    district = request.form['district']
    year = request.form['year']
    taluka = request.form['taluka']
    village = request.form['village']
    area_value = float(request.form['area_value'])
    
    # Initialize progress tracking with unique session ID
    session_id = f"{threading.current_thread().ident}_{int(time.time())}"
    processing_status["scraping_progress"][session_id] = {"step": 0, "message": "Starting..."}
    
    # Store session ID in session for frontend tracking
    session['current_scraping_session'] = session_id
    
    # Get land rate using method2 with progress tracking
    result = get_land_rate_with_progress(district, year, taluka, village, area_value, session_id)
    
    # Clean up progress tracking
    processing_status["scraping_progress"].pop(session_id, None)
    
    # Store result in session to prevent form resubmission
    if 'error' in result:
        session['method2_error'] = result['error']
        session.pop('method2_result', None)
        return jsonify({"status": "error", "message": result['error']})
    else:
        session['method2_result'] = result
        session.pop('method2_error', None)
        return jsonify({"status": "success", "result": result})

def get_land_rate_with_progress(district, year, taluka, village, area_value, session_id):
    """Wrapper function to track progress during scraping"""
    from method2 import IGRScraper
    
    scraper = IGRScraper(headless=True)
    
    try:
        # Step 1: Connecting to database
        processing_status["scraping_progress"][session_id] = {"step": 1, "message": "Connecting to IGR Maharashtra database..."}
        print(f"[PROGRESS] Step 1: Connecting to database")
        scraper.start_browser()
        time.sleep(1)  # Give frontend time to catch up
        
        # Step 2: Navigating to district
        processing_status["scraping_progress"][session_id] = {"step": 2, "message": "Locating district and taluka records..."}
        print(f"[PROGRESS] Step 2: Navigating to {district}")
        url = f"{scraper.base_url}{district}"
        scraper.page.goto(url, wait_until='domcontentloaded')
        time.sleep(1)
        
        # Step 3: Selecting year and taluka
        processing_status["scraping_progress"][session_id] = {"step": 3, "message": "Searching village assessment data..."}
        print(f"[PROGRESS] Step 3: Selecting {year} and {taluka}")
        scraper.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlYear', timeout=15000)
        scraper.page.select_option('#ctl00_ContentPlaceHolder5_ddlYear', label=year)
        time.sleep(2)
        scraper.page.wait_for_load_state('networkidle')
        
        scraper.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlTaluka', timeout=15000)
        scraper.page.select_option('#ctl00_ContentPlaceHolder5_ddlTaluka', label=taluka)
        time.sleep(2)
        scraper.page.wait_for_load_state('networkidle')
        
        # Step 4: Selecting village and loading table
        processing_status["scraping_progress"][session_id] = {"step": 4, "message": "Analyzing land rate tables..."}
        print(f"[PROGRESS] Step 4: Selecting village {village}")
        scraper.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ddlVillage', timeout=15000)
        scraper.page.wait_for_function(
            "document.querySelector('#ctl00_ContentPlaceHolder5_ddlVillage').options.length > 1",
            timeout=10000
        )
        scraper.page.select_option('#ctl00_ContentPlaceHolder5_ddlVillage', label=village)
        time.sleep(2)
        scraper.page.wait_for_load_state('networkidle')
        
        # Step 5: Processing table data
        processing_status["scraping_progress"][session_id] = {"step": 5, "message": "Calculating final rates..."}
        print(f"[PROGRESS] Step 5: Loading table data")
        scraper.page.wait_for_selector('#ctl00_ContentPlaceHolder5_ruralDataGrid', timeout=15000)
        table_html = scraper.page.locator('#ctl00_ContentPlaceHolder5_ruralDataGrid').inner_html()
        time.sleep(1)
        
        # Step 6: Final calculation
        processing_status["scraping_progress"][session_id] = {"step": 6, "message": "Processing complete!"}
        print(f"[PROGRESS] Step 6: Processing complete")
        
        # Parse and return result (using existing logic from method2)
        from bs4 import BeautifulSoup
        import re
        
        full_table_html = f"<table id='ctl00_ContentPlaceHolder5_ruralDataGrid'>{table_html}</table>"
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
                
                # Check if area_value fits in range
                if scraper.is_value_in_range(area_value, assessment_range):
                    try:
                        rate_per_hectare = float(rate_hectares)
                        rate_per_sqm = rate_per_hectare / 10000
                        
                        # Keep progress active for a moment to show completion
                        time.sleep(2)
                        
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
        print(f"[PROGRESS] Error: {str(e)}")
        return {"error": str(e)}
    finally:
        scraper.close_browser()

@app.route('/index_results')
def index_with_results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Get Method 2 results
    method2_result = session.get('method2_result', None)
    method2_error = session.get('method2_error', None)
    
    # Also get Method 1 results if they exist
    result_en = session.get('method1_result_en', None)
    result_mr = session.get('method1_result_mr', None)
    table = session.get('method1_table', None)
    
    return render_template('index.html', 
                         method2_result=method2_result, 
                         method2_error=method2_error,
                         result_en=result_en, 
                         result_mr=result_mr, 
                         table=table)

@app.route('/update', methods=['POST'])
def update_value():
    """POST endpoint to receive and store values from external sources like Google Colab"""
    global latest_value
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data or 'val' not in data:
            return jsonify({"status": "error", "message": "Missing 'val' field in JSON"}), 400
        
        # Store the value
        received_val = data['val']
        latest_value['val'] = received_val
        
        # Print to terminal for debugging
        print(f"[UPDATE] Received value from external source: {received_val}")
        print(f"[UPDATE] Current stored value: {latest_value}")
        
        return jsonify({"status": "success", "received": received_val}), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to process update request: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get', methods=['GET'])
def get_value():
    """GET endpoint to retrieve the latest stored value"""
    global latest_value
    
    try:
        print(f"[GET] Returning stored value: {latest_value}")
        return jsonify(latest_value), 200
        
    except Exception as e:
        print(f"[ERROR] Failed to retrieve value: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/upload', methods=['POST'])
def upload_file():
    """POST endpoint to upload files and process them locally using OCR"""
    
    try:
        # Check if file exists in request
        if 'file' not in request.files:
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        file = request.files['file']
        
        # Check if file is actually selected
        if file.filename == '':
            return jsonify({"status": "error", "message": "No file uploaded"}), 400
        
        # Validate file type (jpg/png)
        allowed_extensions = {'jpg', 'jpeg', 'png'}
        file_extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_extension not in allowed_extensions:
            return jsonify({"status": "error", "message": "Only JPG and PNG files are allowed"}), 400
        
        try:
            print(f"[UPLOAD] Received file: {file.filename} ({file.mimetype})")
            
            # Set image processing flag
            processing_status["image_processing"] = True
            
            # Save uploaded file to temporary location
            with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{file_extension}') as temp_file:
                file.save(temp_file.name)
                temp_file_path = temp_file.name
            
            print(f"[OCR] Processing image locally: {temp_file_path}")
            
            # Initialize OCR processor and process image
            ocr = initialize_ocr()
            ocr_results = ocr.process_image(temp_file_path)
            
            # Clean up temporary file
            os.unlink(temp_file_path)
            
            print(f"[OCR] Local OCR results: {ocr_results}")
            
            # Calculate assessment value (assessment / total_cultivable_area)
            try:
                assessment = ocr_results.get('assessment')
                total_cultivable_area = ocr_results.get('total_cultivable_area')
                
                if assessment and total_cultivable_area:
                    # Handle different formats like '6.25.00' -> 6.25 or '0.02.00' -> 0.02
                    assessment_val = float(assessment)
                    
                    # For total_cultivable_area, handle formats like '0.02.00' -> 0.02
                    if total_cultivable_area.count('.') > 1:
                        # Split by dots and take first two parts: '0.02.00' -> '0.02'
                        parts = total_cultivable_area.split('.')
                        total_area_val = float(f"{parts[0]}.{parts[1]}")
                    else:
                        total_area_val = float(total_cultivable_area)
                    
                    calculated_assessment = assessment_val / total_area_val
                    
                    print(f"[CALCULATION] Assessment: {assessment} -> {assessment_val}")
                    print(f"[CALCULATION] Total Area: {total_cultivable_area} -> {total_area_val}")
                    print(f"[CALCULATION] Calculated Assessment Value: {calculated_assessment}")
                    
                    # Clear image processing flag
                    processing_status["image_processing"] = False
                    
                    # Return enhanced response with calculated value
                    return jsonify({
                        "status": "success",
                        "raw_data": ocr_results,
                        "calculated_assessment_value": round(calculated_assessment, 4),
                        "assessment": assessment,
                        "total_cultivable_area": total_cultivable_area
                    }), 200
                else:
                    processing_status["image_processing"] = False
                    return jsonify({
                        "status": "error",
                        "message": "Missing assessment or total_cultivable_area in OCR results",
                        "raw_data": ocr_results
                    }), 400
                    
            except (ValueError, ZeroDivisionError) as e:
                processing_status["image_processing"] = False
                print(f"[ERROR] Calculation failed: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"Failed to calculate assessment value: {str(e)}",
                    "raw_data": ocr_results
                }), 400
                
        except Exception as e:
            processing_status["image_processing"] = False
            print(f"[ERROR] Local OCR processing failed: {str(e)}")
            return jsonify({"status": "error", "message": f"OCR processing failed: {str(e)}"}), 500
        
    except Exception as e:
        processing_status["image_processing"] = False
        print(f"[ERROR] File upload processing failed: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
