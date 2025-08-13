# resumeparser.py

import yaml
import json
from openai import OpenAI
import google.generativeai as genai
import ollama
from ollama import ResponseError

# --- CONFIGURATION ---

def load_config():
    """Loads API keys and model configs from the configuration file."""
    try:
        with open("config.yaml") as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
            return config
    except FileNotFoundError:
        print("ERROR: config.yaml not found. Please create it.")
        return {}

config = load_config()
OPENAI_KEY = config.get("OPENAI_API_KEY")
GOOGLE_KEY = config.get("GOOGLE_API_KEY")
OLLAMA_MODEL = config.get("OLLAMA_MODEL", "llama3") # Default to llama3 if not set

# Configure online clients
if GOOGLE_KEY and GOOGLE_KEY != "YOUR GEMINI KEY HERE":
    genai.configure(api_key=GOOGLE_KEY)

# --- PROMPT DEFINITION ---

SYSTEM_PROMPT = """
You are a highly efficient and accurate ATS (Applicant Tracking System) bot. Your purpose is to parse a resume text and extract a comprehensive set of information into a structured JSON format.

Given the resume text, extract the following fields with precision:
1.  **full_name**: The full name of the candidate.
2.  **contact_information**: An object containing:
    * **email**: The primary email address.
    * **phone**: The phone number. If not present, return null.
3.  **professional_links**: An object containing:
    * **linkedin**: The full URL to their LinkedIn profile. If not present, return null.
    * **github**: The full URL to their GitHub profile. If not present, return null.
    * **portfolio**: Any other portfolio or personal website URL. If not present, return null.
4.  **summary**: A brief professional summary or objective statement from the resume.
5.  **experience**: A list of objects, where each object represents a job and has the following fields:
    * **company**: The name of the company.
    * **position**: The job title or position held.
    * **duration**: The employment dates or duration (e.g., "Jan 2020 - Present" or "3 years").
    * **responsibilities**: A list of key responsibilities, accomplishments, or a summary of the role.
6.  **education**: A list of objects, each with "institution", "degree", and "graduation_date".
7.  **skills**: An object containing:
    * **technical**: A list of all technical skills (e.g., Python, React, SQL, AWS, Docker).
    * **soft**: A list of all soft skills (e.g., Communication, Teamwork, Leadership, Problem-solving).
8.  **certifications**: A list of any certifications mentioned.

IMPORTANT: Your response MUST be a valid JSON object and nothing else. Do not include any introductory text, explanations, or markdown formatting like ```json.
"""

# --- LLM API CALLS ---

def _call_openai(resume_data):
    """Calls the OpenAI GPT model."""
    if not OPENAI_KEY or OPENAI_KEY == "YOUR OPENAI KEY HERE":
        raise ValueError("OpenAI API key is missing or not set in config.yaml")
        
    client = OpenAI(api_key=OPENAI_KEY)
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": resume_data}
        ],
        temperature=0.0,
        max_tokens=2048, # Increased max_tokens for more detailed resumes
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

def _call_gemini(resume_data):
    """Calls the Google Gemini Pro model."""
    if not GOOGLE_KEY or GOOGLE_KEY == "YOUR GEMINI KEY HERE":
        raise ValueError("Google API key is missing or not set in config.yaml")

    model = genai.GenerativeModel('gemini-pro')
    full_prompt = f"{SYSTEM_PROMPT}\n\nResume Text:\n{resume_data}"
    
    # Add generation config for Gemini to encourage JSON output
    generation_config = genai.types.GenerationConfig(
        temperature=0.0,
        max_output_tokens=2048,
        response_mime_type="application/json"
    )

    response = model.generate_content(full_prompt, generation_config=generation_config)
    
    cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
    return cleaned_response

def _call_ollama(resume_data):
    """Calls a local Ollama model."""
    try:
        client = ollama.Client()
        # Check if the model exists locally, if not, pull it
        try:
            client.show(OLLAMA_MODEL)
        except ResponseError as e:
            if e.status_code == 404:
                print(f"Model '{OLLAMA_MODEL}' not found locally. Pulling it now...")
                ollama.pull(OLLAMA_MODEL)
                print(f"Model '{OLLAMA_MODEL}' pulled successfully.")
            else:
                raise
    
        response = client.chat(
            model=OLLAMA_MODEL,
            messages=[
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': resume_data},
            ],
            format='json' # Use Ollama's built-in JSON mode
        )
        return response['message']['content']
    except Exception as e:
        # This will catch connection errors if the Ollama server isn't running
        raise ConnectionError(f"Could not connect to Ollama server or the model '{OLLAMA_MODEL}' is not available. Is Ollama running?") from e

# --- MAIN EXTRACTOR FUNCTION ---

def extract_resume_data(resume_data, provider="gemini"):
    """
    Extracts information from resume text using the specified LLM provider.
    """
    try:
        if provider == "openai":
            return _call_openai(resume_data)
        elif provider == "gemini":
            return _call_gemini(resume_data)
        elif provider == "ollama":
            return _call_ollama(resume_data)
        else:
            raise ValueError(f"Invalid provider specified: {provider}. Choose 'openai', 'gemini', or 'ollama'.")
            
    except Exception as e:
        print(f"An error occurred with provider {provider}: {e}")
        error_response = {
            "error": True,
            "message": str(e),
            "provider": provider
        }
        return json.dumps(error_response, indent=4)
