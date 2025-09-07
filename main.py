from flask import Flask, render_template, request, redirect, url_for, session
import os
from dotenv import load_dotenv
from method1 import process_data
from method2 import get_land_rate

load_dotenv()

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

if __name__ == '__main__':
    app.run(debug=True, port=5001)
