# app.py

import os
import json
from flask import Flask, request, render_template, flash, redirect, url_for
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from resumeparser import extract_resume_data

# --- SETUP ---

UPLOAD_FOLDER = '__DATA__'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a-super-secret-key-for-flash-messages' # Needed for flash()

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- HELPER FUNCTIONS ---

def allowed_file(filename):
    """Check if the file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def read_pdf(path):
    """Extract text from a PDF file."""
    try:
        reader = PdfReader(path)
        data = ""
        for page in reader.pages:
            data += page.extract_text()
        return data
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/process", methods=["POST"])
def process_resume():
    if 'pdf_doc' not in request.files:
        flash('No file part in the request.')
        return redirect(url_for('index'))

    file = request.files['pdf_doc']
    provider = request.form.get('provider', 'gemini') # Default to Gemini if not provided

    if file.filename == '':
        flash('No file selected.')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 1. Extract text from PDF
        resume_text = read_pdf(filepath)
        os.remove(filepath) # Clean up the saved file immediately

        if not resume_text:
            flash('Could not extract text from the PDF. The file might be empty or corrupted.')
            return redirect(url_for('index'))
            
        # 2. Call the resume parser
        extracted_data_json_str = extract_resume_data(resume_text, provider=provider)
        
        # 3. Parse the JSON string for rendering
        try:
            # The function returns a string, so we load it into a Python dict
            data_dict = json.loads(extracted_data_json_str)
            return render_template('index.html', data=data_dict, provider=provider)
        except json.JSONDecodeError:
            flash(f"Failed to parse the response from the AI. Raw response: {extracted_data_json_str}")
            return redirect(url_for('index'))
    else:
        flash('Invalid file type. Please upload a PDF.')
        return redirect(url_for('index'))

if __name__ == "__main__":
    # Use debug=False for production
    app.run(port=8000, debug=True)