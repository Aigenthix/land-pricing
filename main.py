from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import requests
from dotenv import load_dotenv
from method1 import process_data
from method2 import get_land_rate

load_dotenv()

# Global variable to store latest value from external sources
latest_value = {"val": None}

# Colab URL for file processing (replace <colab-ngrok-url> with actual ngrok URL)
COLAB_URL = "https://b1ef6ad913b3.ngrok-free.app/process"

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

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
    return render_template('index.html')

@app.route('/clear_results')
def clear_results():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    # Clear all method results from session
    session.pop('method1_result_en', None)
    session.pop('method1_result_mr', None)
    session.pop('method1_table', None)
    session.pop('method2_result', None)
    session.pop('method2_error', None)
    
    return redirect(url_for('index'))

@app.route('/process', methods=['POST'])
def process():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    docx_file = request.files['input_file']
    excluded_survey_numbers = request.form['excluded_survey_numbers']
    result_en, result_mr, table = process_data(docx_file.read(), excluded_survey_numbers)
    
    # Store results in session to prevent form resubmission
    session['method1_result_en'] = result_en
    session['method1_result_mr'] = result_mr
    session['method1_table'] = table.to_html(classes='data', header=True)
    
    return redirect(url_for('index_with_method1_results'))

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

@app.route('/process_method2', methods=['POST'])
def process_method2():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    
    district = request.form['district']
    year = request.form['year']
    taluka = request.form['taluka']
    village = request.form['village']
    area_value = float(request.form['area_value'])
    
    # Get land rate using method2
    result = get_land_rate(district, year, taluka, village, area_value)
    
    # Store result in session to prevent form resubmission
    if 'error' in result:
        session['method2_error'] = result['error']
        session.pop('method2_result', None)
    else:
        session['method2_result'] = result
        session.pop('method2_error', None)
    
    return redirect(url_for('index_with_results'))

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
    """POST endpoint to upload files and forward them to Colab for processing"""
    
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
        
        print(f"[UPLOAD] Received file: {file.filename} ({file.mimetype})")
        
        # Forward file to Colab
        try:
            # Prepare file for forwarding
            file.stream.seek(0)  # Reset stream position
            files = {"file": (file.filename, file.stream, file.mimetype)}
            
            print(f"[UPLOAD] Forwarding file to Colab: {COLAB_URL}")
            
            # Send POST request to Colab
            response = requests.post(COLAB_URL, files=files, timeout=60)
            
            print(f"[UPLOAD] Colab response status: {response.status_code}")
            
            # Return Colab's JSON response directly to client
            if response.headers.get('content-type', '').startswith('application/json'):
                colab_data = response.json()
                print(f"[UPLOAD] Colab response: {colab_data}")
                return jsonify(colab_data), response.status_code
            else:
                # If Colab doesn't return JSON, return the text response
                return jsonify({"status": "success", "response": response.text}), response.status_code
                
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Failed to forward file to Colab: {str(e)}")
            return jsonify({"status": "error", "message": f"Failed to connect to Colab: {str(e)}"}), 500
        
    except Exception as e:
        print(f"[ERROR] File upload processing failed: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
