# land-pricing
*There is a lot of code files here, this is because I required two different methods and have kept them both in the same branch*

### 1. First, Install UV and install dependencies
```bash
uv venv
uv sync
```

### 2. Create a `.env` file in the /root directory of the format below and enter the Gemini API key.
```
GOOGLE_API_KEY=''
```
- Input your API key between the quotes

### 3. Install Playwright inside your venv
```bash
source venv/bin/activate # this is for linux
playwright install
```

### 4. After syncing and installing dependencies, you may run the application
```bash
gunicorn --workers 1 --threads 2 --bind 0.0.0.0:5001 --timeout 120 main:app
```
- This runs the app on port `5001`


## For DEMO
### 1. In tab 1
- In the input box, upload the file --> `index2/files/majiwada_index2.pdf`
- This file contains the index documents for the *Village* = `Majivade`, *District* = `Thane`, *Taluka* = `Thane`
- Using the gemini API key, it will do the OCR and make the table

### 2. In Tab 2
- Since we previously used the index documents for *Village* = `Majivade`, *District* = `Thane`, *Taluka* = `Thane`
- Now, we upload the *11 notification* for the survey numbers we want to get the price on
- Upload the `index2/11Notification.docx`
- Enter the year we use (right now we are using `2023-2024` due to the same year being used for calculation of Tab 1)
- Enter the district, taluka and village details
- Click on Process
- It processes and does all the matching and gives out the final output

### 3. Tab 3
- Click the button and show the answer

