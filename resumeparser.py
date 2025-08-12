# resumeparser.py

import yaml
import json
from openai import OpenAI
import google.generativeai as genai

# --- CONFIGURATION ---

def load_api_keys():
    """Loads API keys from the configuration file."""
    try:
        with open("config.yaml") as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
            return config.get("OPENAI_API_KEY"), config.get("GOOGLE_API_KEY")
    except FileNotFoundError:
        print("ERROR: config.yaml not found. Please create it.")
        return None, None

OPENAI_KEY, GOOGLE_KEY = load_api_keys()

# Configure the Gemini client
if GOOGLE_KEY:
    genai.configure(api_key=GOOGLE_KEY)

# --- PROMPT DEFINITION ---

SYSTEM_PROMPT = """
You are an expert ATS (Applicant Tracking System) bot. Your sole purpose is to parse a resume text and extract key information in a structured JSON format.

Given the resume text, extract the following fields:
1.  **full_name**: The full name of the candidate.
2.  **email**: The primary email address.
3.  **github**: The full URL to their GitHub profile. If not present, return null.
4.  **linkedin**: The full URL to their LinkedIn profile. If not present, return null.
5.  **employment_details**: A list of objects, where each object has "company", "position", and "duration".
6.  **technical_skills**: A list of all technical skills (e.g., Python, React, SQL, AWS).
7.  **soft_skills**: A list of all soft skills (e.g., Communication, Teamwork, Leadership).

IMPORTANT: Respond with ONLY the JSON object. Do not include any introductory text, explanations, or markdown formatting like ```json. Your entire response must be a valid JSON.
"""

# --- LLM API CALLS ---

def _call_openai(resume_data):
    """Calls the OpenAI GPT model."""
    if not OPENAI_KEY:
        raise ValueError("OpenAI API key is missing from config.yaml")
        
    client = OpenAI(api_key=OPENAI_KEY)
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": resume_data}
        ],
        temperature=0.0,
        max_tokens=1500,
        response_format={"type": "json_object"} # Use JSON mode
    )
    return response.choices[0].message.content

def _call_gemini(resume_data):
    """Calls the Google Gemini Pro model."""
    if not GOOGLE_KEY:
        raise ValueError("Google API key is missing from config.yaml")

    model = genai.GenerativeModel('gemini-pro')
    # Gemini requires the prompt to be structured differently
    full_prompt = f"{SYSTEM_PROMPT}\n\nResume Text:\n{resume_data}"
    
    response = model.generate_content(full_prompt)
    
    # Clean up the response to ensure it's valid JSON
    # Gemini might sometimes include ```json ... ``` which we need to remove.
    cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
    return cleaned_response
    
# --- MAIN EXTRACTOR FUNCTION ---

def extract_resume_data(resume_data, provider="gemini"):
    """
    Extracts information from resume text using the specified LLM provider.

    Args:
        resume_data (str): The text content of the resume.
        provider (str): The LLM provider to use ('openai' or 'gemini').

    Returns:
        str: A JSON string of the extracted data.
    """
    try:
        if provider == "openai":
            return _call_openai(resume_data)
        elif provider == "gemini":
            return _call_gemini(resume_data)
        else:
            raise ValueError(f"Invalid provider specified: {provider}. Choose 'openai' or 'gemini'.")
            
    except Exception as e:
        print(f"An error occurred with provider {provider}: {e}")
        # Return an error structure in JSON format
        error_response = {
            "error": True,
            "message": str(e),
            "provider": provider
        }
        return json.dumps(error_response, indent=4)