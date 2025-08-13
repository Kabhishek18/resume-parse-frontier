# batch_validator.py

import os
import pandas as pd
import requests
import logging
import json
import docx
from pypdf import PdfReader
import math
import re
from datetime import datetime
from resumeparser import extract_resume_data

# --- CONFIGURATION ---
# Instead of a CSV, provide the list of resume URLs to process directly here.
RESUME_URLS = [
    "https://assets.jobsforher.com/uploads/v3/community/resumes/bfd866394f0f36ad6b930c47d04a89_aartisingh%20resume.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/3c93aaab0077d354669cbd7b834c40_Resume_10_10_2023_10_53_21_am.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/114f007588acd07ede442a1be0f750_Sumbul%20Ansari%20Resume-1.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/0e11cc2e625cb187327168ba239d15_inbound7319120864111437090.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/a3471242ac765b4b895c96ac2c84c1_Lakshmi_CN_CV.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/515b476f1057cf99cb930144779f38_1664786635769_Arifa%20Resume.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/e10b5e8a3dfed6362b193389c7a392_SHEFINA%2011.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/8b8e0e953ab83b503e134330b9230f_APCV.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/d6a1941ff15dd012ec199bb24ca546_48260030-DOC-20230710-WA0024.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/f051c64dddae22468208badbb8aeb7_Resume_Neha%20Gupta-converted.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/c11586c0b83d0eb1a9cf5019272616_keerthana%20.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/3504ede1365ce5dc19b0463658f26e_Sanjana%20CV%20(1)-2.docx", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/3a2b9819b048587dd8c57f0fd4fc9f_Esha%20Atha%20Resume%20999%20(1).pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/4f27fe635c9852c7436425b8dea696_DOC-20230325-WA0010-1.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/5a2f3bb683067d30eb871e0e5a4de9_JanaviY_11.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/a6d399d7974ca677a86640058bb768_Resume.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/9702b0ce41a4833511613c9b8633b8_Resume%20Lt%20Col%20Ipsa%20O%20%20Ratha.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/d51229270f80aa08f8208751e0be71_Resume-Sakshi%20Malik.pdf", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/a13948aec12526bc28241c6aeb3ef2_Resume%20Roly%20Sinha.doc", 
    "https://assets.jobsforher.com/uploads/v3/community/resumes/69839e69a3c6dc14d37c5b2ed1ab3b_Priya%20Resume.pdf"
]

OUTPUT_REPORT_PATH = 'extraction_report.csv'
DOWNLOAD_FOLDER = 'temp_resumes_for_extraction'
JSON_OUTPUT_FOLDER = '__BATCH_OUTPUTS__' # New folder for individual JSON files
PROVIDER = 'ollama'  # Choose 'gemini', 'openai', or 'ollama'

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Create output folder if it doesn't exist
os.makedirs(JSON_OUTPUT_FOLDER, exist_ok=True)

# --- HELPER FUNCTIONS ---

def download_file(url, folder):
    """Downloads a file from a URL into the specified temporary folder."""
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        
        filename = url.split('/')[-1].split('?')[0] or f"resume_{hash(url)}"
        
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' in content_type and not filename.lower().endswith('.pdf'):
            filename += '.pdf'
        elif 'word' in content_type and not (filename.lower().endswith('.docx') or filename.lower().endswith('.doc')):
            filename += '.docx'

        filepath = os.path.join(folder, filename)
        with open(filepath, 'wb') as f:
            f.write(response.content)
        logging.info(f"Downloaded: {url}")
        return filepath
    except requests.exceptions.RequestException as e:
        logging.error(f"Download failed for {url}. Error: {e}")
        return None

def read_resume_text(filepath):
    """Reads text from a downloaded PDF or DOCX file. Skips .doc files."""
    if not filepath: return None
    try:
        if filepath.lower().endswith('.pdf'):
            reader = PdfReader(filepath)
            return "".join(page.extract_text() for page in reader.pages)
        elif filepath.lower().endswith('.docx'):
            doc = docx.Document(filepath)
            return "\n".join(para.text for para in doc.paragraphs)
        elif filepath.lower().endswith('.doc'):
            logging.warning(f"Skipping unsupported .doc file: {filepath}. Please convert to DOCX or PDF for processing.")
            return None
        return None
    except Exception as e:
        logging.error(f"Could not read text from {filepath}. Error: {e}")
        return None

def calculate_experience_fallback(experience_list):
    """Calculates total years of experience as a fallback if the AI doesn't provide it."""
    if not experience_list:
        return 0

    years = []
    for job in experience_list:
        # FIX: Ensure duration is a string before processing to prevent TypeError.
        duration = str(job.get('duration', ''))
        # Find all 4-digit numbers which are likely years
        found_years = re.findall(r'\b(19[89]\d|20\d\d)\b', duration)
        if found_years:
            years.extend([int(y) for y in found_years])

    if not years:
        return 0
    
    # Calculate the difference between the latest and earliest year found
    return max(years) - min(years) if len(years) > 1 else 1


def flatten_parsed_data(parsed_data):
    """Flattens the complex JSON object into a simple dictionary for CSV export."""
    flat_data = {}
    flat_data['FullName'] = parsed_data.get('full_name')
    flat_data['Email'] = parsed_data.get('contact_information', {}).get('email')
    flat_data['Phone'] = parsed_data.get('contact_information', {}).get('phone')
    flat_data['LinkedIn'] = parsed_data.get('professional_links', {}).get('linkedin')
    flat_data['GitHub'] = parsed_data.get('professional_links', {}).get('github')
    flat_data['Portfolio'] = parsed_data.get('professional_links', {}).get('portfolio')
    flat_data['Summary'] = parsed_data.get('summary')
    
    experience = parsed_data.get('experience', [])
    years_of_exp = parsed_data.get('total_experience_years', 0)

    # Use the fallback calculation if the AI returns 0 or the field is missing
    if not years_of_exp and experience:
        years_of_exp = calculate_experience_fallback(experience)

    flat_data['YearsOfExperience'] = years_of_exp

    # Key fields for analysis
    flat_data['Title'] = ''
    flat_data['Company'] = ''
    if experience:
        latest_job = experience[0]
        flat_data['Title'] = latest_job.get('position', '')
        flat_data['Company'] = latest_job.get('company', '')
        exp_strings = [f"{job.get('position', '')} at {job.get('company', '')} ({job.get('duration', '')})" for job in experience]
        flat_data['FullExperience'] = " | ".join(exp_strings)
    else:
        flat_data['FullExperience'] = ''

    skills = parsed_data.get('skills', {})
    flat_data['Skills'] = ', '.join(skills.get('technical', []) + skills.get('soft', []))

    return flat_data

# --- MAIN SCRIPT ---

def run_extraction():
    """Main function to execute the batch extraction."""
    if not RESUME_URLS:
        logging.warning("The RESUME_URLS list is empty. Please add URLs to the script.")
        return

    extraction_results = []

    for url in RESUME_URLS:
        logging.info(f"--- Processing URL: {url} ---")
        result_row = {'Resume_URL': url}

        if not isinstance(url, str) or not url.startswith('http'):
            result_row['Status'] = 'Skipped - Invalid URL'
            extraction_results.append(result_row)
            continue

        # Each resume is downloaded to a temp file for processing
        filepath = download_file(url, DOWNLOAD_FOLDER)
        if not filepath:
            result_row['Status'] = 'Failed - Download'
            extraction_results.append(result_row)
            continue

        resume_text = read_resume_text(filepath)
        if not resume_text:
            result_row['Status'] = 'Failed - Text Extraction or Unsupported .doc'
            extraction_results.append(result_row)
            if os.path.exists(filepath):
                os.remove(filepath)
            continue
            
        parser_output_str = extract_resume_data(resume_text, provider=PROVIDER)
        
        try:
            parsed_data = json.loads(parser_output_str)
            if parsed_data.get("error"):
                result_row['Status'] = f"Failed - Parser Error: {parsed_data.get('message')}"
            else:
                # --- New Feature: Save individual JSON output ---
                full_name = parsed_data.get('full_name', 'parsed_resume')
                # Sanitize the filename to make it safe for file systems
                safe_filename = "".join([c for c in full_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
                safe_filename = safe_filename.replace(' ', '_') + '.json'
                output_filepath = os.path.join(JSON_OUTPUT_FOLDER, safe_filename)

                with open(output_filepath, 'w') as json_file:
                    json.dump(parsed_data, json_file, indent=4)
                logging.info(f"Saved parsed JSON to {output_filepath}")
                # --- End of new feature ---

                flat_data = flatten_parsed_data(parsed_data)
                result_row.update(flat_data)
                result_row['Status'] = 'Processed'
        except json.JSONDecodeError:
            result_row['Status'] = 'Failed - JSON Decode'
        
        extraction_results.append(result_row)
        # The temp file is removed after processing
        if os.path.exists(filepath):
            os.remove(filepath)

    column_order = [
        'Resume_URL', 'Status', 'Title', 'YearsOfExperience', 'Company', 'Skills', 
        'FullName', 'Email', 'Phone', 'LinkedIn', 'GitHub', 'Portfolio', 'Summary', 'FullExperience'
    ]
    
    report_df = pd.DataFrame(extraction_results)
    
    existing_columns = [col for col in column_order if col in report_df.columns]
    report_df = report_df[existing_columns]

    report_df.to_csv(OUTPUT_REPORT_PATH, index=False)
    logging.info(f"--- Extraction complete. Report saved to '{OUTPUT_REPORT_PATH}' ---")

if __name__ == "__main__":
    run_extraction()
