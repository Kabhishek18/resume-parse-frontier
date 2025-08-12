# app.py

import os
import json
import docx
from flask import Flask, request, render_template, flash, redirect, url_for
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from resumeparser import extract_resume_data

# --- SETUP ---

UPLOAD_FOLDER = '__DATA__'
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a-super-secret-key-for-flash-messages'

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

def read_docx(path):
    """Extract text from a DOCX file."""
    try:
        doc = docx.Document(path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        print(f"Error reading DOCX: {e}")
        return None

# --- ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route("/process", methods=["POST"])
def process_resume():
    if 'resume_doc' not in request.files:
        flash('No file part in the request.', 'error')
        return redirect(url_for('index'))

    file = request.files['resume_doc']
    provider = request.form.get('provider', 'gemini')

    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        resume_text = None
        file_extension = filename.rsplit('.', 1)[1].lower()

        if file_extension == 'pdf':
            resume_text = read_pdf(filepath)
        elif file_extension == 'docx':
            resume_text = read_docx(filepath)
        
        os.remove(filepath)

        if not resume_text:
            error_message = f'Could not extract text from the {file_extension.upper()} file. It might be empty, corrupted, or password-protected.'
            return render_template('index.html', error=error_message, provider=provider)
            
        extracted_data_json_str = extract_resume_data(resume_text, provider=provider)
        
        try:
            data_dict = json.loads(extracted_data_json_str)
            # If the dictionary contains an 'error' key, it means the parser failed.
            if data_dict.get("error"):
                 error_message = data_dict.get('message', 'An unknown error occurred.')
                 return render_template('index.html', error=error_message, provider=provider)
            
            # Success case
            return render_template('index.html', data=data_dict, provider=provider)

        except json.JSONDecodeError:
            error_message = f"Failed to parse the response from the AI. This often happens with model timeouts or unexpected outputs. Raw response: {extracted_data_json_str}"
            return render_template('index.html', error=error_message, provider=provider)
    else:
        flash('Invalid file type. Please upload a PDF or DOCX file.', 'error')
        return redirect(url_for('index'))

if __name__ == "__main__":
    # Use python app.py to run with these settings
    app.run(port=8000, debug=True)
