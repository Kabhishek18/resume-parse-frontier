# app.py

import os
import json
import docx
import logging
from flask import Flask, request, render_template, flash, redirect, url_for
from pypdf import PdfReader
from werkzeug.utils import secure_filename
from resumeparser import extract_resume_data

# --- SETUP ---

UPLOAD_FOLDER = '__DATA__'
OUTPUT_FOLDER = '__OUTPUTS__' # New folder for JSON outputs
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = 'a-super-secret-key-for-flash-messages'

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True) # Create output folder if it doesn't exist

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
        app.logger.error(f"Error reading PDF: {e}")
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
        app.logger.error(f"Error reading DOCX: {e}")
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
    app.logger.info(f"Processing request with provider: {provider}")

    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        app.logger.info(f"File '{filename}' saved temporarily.")

        resume_text = None
        file_extension = filename.rsplit('.', 1)[1].lower()

        if file_extension == 'pdf':
            resume_text = read_pdf(filepath)
        elif file_extension == 'docx':
            resume_text = read_docx(filepath)
        
        os.remove(filepath)
        app.logger.info(f"Temporary file '{filename}' removed.")

        if not resume_text:
            error_message = f'Could not extract text from the {file_extension.upper()} file. It might be empty, corrupted, or password-protected.'
            app.logger.error(error_message)
            return render_template('index.html', error=error_message, provider=provider)
            
        app.logger.info("Text extracted successfully. Calling resume parser...")
        extracted_data_json_str = extract_resume_data(resume_text, provider=provider)
        app.logger.debug(f"Raw response from parser: {extracted_data_json_str}")
        
        try:
            # Parse the JSON string to a Python dictionary
            data_dict = json.loads(extracted_data_json_str)
            app.logger.debug(f"Parsed dictionary from parser: {data_dict}")

            # If the dictionary contains an 'error' key, it means the parser failed.
            if data_dict.get("error"):
                 error_message = data_dict.get('message', 'An unknown error occurred.')
                 app.logger.error(f"Error returned from resumeparser: {error_message}")
                 return render_template('index.html', error=error_message, provider=provider)
            
            # --- New Feature: Save output to a name-based JSON file ---
            full_name = data_dict.get('full_name', 'parsed_resume')
            # Sanitize the filename to make it safe for file systems
            safe_filename = "".join([c for c in full_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
            safe_filename = safe_filename.replace(' ', '_') + '.json'
            output_filepath = os.path.join(OUTPUT_FOLDER, safe_filename)
            
            with open(output_filepath, 'w') as json_file:
                json.dump(data_dict, json_file, indent=4)
            app.logger.info(f"Successfully saved parsed data to {output_filepath}")

            # --- Fix for UI display ---
            # The template expects a dictionary to render the fields, so we pass data_dict
            app.logger.info("Successfully parsed data. Rendering results page.")
            return render_template('index.html', data=data_dict, provider=provider)

        except json.JSONDecodeError:
            error_message = f"Failed to parse the response from the AI. This often happens with model timeouts or unexpected outputs. Raw response: {extracted_data_json_str}"
            app.logger.error(error_message)
            return render_template('index.html', error=error_message, provider=provider)
    else:
        flash('Invalid file type. Please upload a PDF or DOCX file.', 'error')
        return redirect(url_for('index'))

if __name__ == "__main__":
    # Use 'python app.py' to run with these settings
    app.run(port=5000, debug=True)
