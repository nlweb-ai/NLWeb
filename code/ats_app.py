# code/ats_app.py
from flask import Flask, render_template, request
import requests # For making HTTP requests
import json     # For handling JSON data
import uuid     # For generating unique IDs for jobs
import asyncio  # For running async data loading functions
import os       # For path joining if needed for temp files (though handled in loader)

# Attempt to import the new data loading function and site name
try:
    from code.tools.ats_data_loader import add_job_posting_data, ATS_JOBS_SITE_NAME, \
                                           add_candidate_profile_data, ATS_CANDIDATES_SITE_NAME
except ImportError as e:
    print(f"Error importing from code.tools.ats_data_loader: {e}")
    # Fallback or define a dummy function if essential for app to load
    async def add_job_posting_data(job_data_list, site_name, delete_existing=False):
        print(f"Dummy add_job_posting_data called for {site_name} with {len(job_data_list)} items.")
        return
    async def add_candidate_profile_data(candidate_data_list, site_name, delete_existing=False):
        print(f"Dummy add_candidate_profile_data called for {site_name} with {len(candidate_data_list)} items.")
        return
    ATS_JOBS_SITE_NAME = "ats_jobs_fallback"
    ATS_CANDIDATES_SITE_NAME = "ats_candidates_fallback"


app = Flask(__name__, template_folder='ats_templates')

NLWEB_API_URL = "http://localhost:8000/ask" # NLWeb runs on port 8000

@app.route('/')
def index():
    return render_template('ats_index.html')

@app.route('/create_job', methods=['GET', 'POST'])
def create_job():
    if request.method == 'POST':
        job_title = request.form.get('title')
        job_description = request.form.get('description')
        job_skills_str = request.form.get('skills', '')
        job_skills = [skill.strip() for skill in job_skills_str.split(',') if skill.strip()]
        
        if not job_title or not job_description:
            return "Job title and description are required.", 400

        new_job_data = {
            "id": f"job_{uuid.uuid4()}",
            "title": job_title,
            "description": job_description,
            "required_skills": job_skills,
            "nice_to_have_skills": [], 
            "experience_years": 0 
        }
        
        try:
            print(f"Preparing to add job posting: {new_job_data['id']}")
            asyncio.run(add_job_posting_data(
                job_data_list=[new_job_data], 
                site_name=ATS_JOBS_SITE_NAME, 
                delete_existing=False
            ))
            return f"Job posting '{job_title}' submitted successfully (ID: {new_job_data['id']}). Check server logs for loading status."
        except Exception as e:
            print(f"Error during job posting submission or data loading call: {e}")
            return f"An error occurred while submitting the job posting: {str(e)}", 500
            
    return render_template('create_job.html')

@app.route('/submit_resume', methods=['GET', 'POST'])
def submit_resume():
    if request.method == 'POST':
        candidate_name = request.form.get('name')
        resume_text = request.form.get('resume_text')
        # resume_file = request.files.get('resume_file') # For future file handling

        if not candidate_name or not resume_text:
            return "Candidate name and resume text are required.", 400

        # In a real app, you would parse the resume_text to extract skills, experience, etc.
        # For now, we'll store the raw text and some placeholders.
        new_candidate_data = {
            "id": f"cand_{uuid.uuid4()}", # Ensure uuid is imported
            "name": candidate_name,
            "email": "", # Placeholder - could attempt to extract from resume_text
            "skills": [], # Placeholder - could attempt basic keyword extraction from resume_text
            "experience": [], # Placeholder - could attempt to parse from resume_text
            "resume_text": resume_text
            # Ensure this structure matches what your Qdrant/NLWeb expects for Person schema
        }
        
        try:
            print(f"Preparing to add candidate profile: {new_candidate_data['id']}")
            # Call the imported async function to add the candidate profile data
            asyncio.run(add_candidate_profile_data(
                candidate_data_list=[new_candidate_data], 
                site_name=ATS_CANDIDATES_SITE_NAME, 
                delete_existing=False # Don't delete other profiles when adding a new one
            ))
            return f"Resume for '{candidate_name}' submitted successfully (ID: {new_candidate_data['id']}). Check server logs for loading status."
        except Exception as e:
            print(f"Error during resume submission or data loading call: {e}")
            return f"An error occurred while submitting the resume: {str(e)}", 500
            
    return render_template('submit_resume.html')

@app.route('/search_candidates')
def search_candidates_form():
    return render_template('search_candidates.html')

@app.route('/search_results', methods=['POST'])
def search_candidates_results():
    user_query = request.form.get('query', '')
    if not user_query:
        return "Please enter a search query.", 400

    nlweb_payload = {
        "query": user_query,
        "site": ATS_CANDIDATES_SITE_NAME, # Use the constant
        "item_type": "{http://schema.org/}Person",
        "prompt_name": "ATSCandidateRankingPrompt",
        "generate_mode": "generate",
        "streaming": "False"
    }

    nlweb_response_data = {}
    error_message = None

    try:
        print(f"Sending payload to NLWeb: {nlweb_payload}")
        response = requests.post(NLWEB_API_URL, json=nlweb_payload, timeout=30)
        response.raise_for_status()
        nlweb_response_data = response.json()
        print(f"Received response from NLWeb: {nlweb_response_data}")
    except requests.exceptions.HTTPError as http_err:
        error_message = f"HTTP error occurred: {http_err} - {response.text if response else 'No response text'}"
    except requests.exceptions.ConnectionError as conn_err:
        error_message = f"Connection error occurred: {conn_err}. Ensure NLWeb server is running at {NLWEB_API_URL}."
    except requests.exceptions.Timeout as timeout_err:
        error_message = f"Request timed out: {timeout_err}."
    except requests.exceptions.RequestException as req_err:
        error_message = f"An error occurred with the request: {req_err}."
    except json.JSONDecodeError:
        error_message = f"Failed to decode JSON response from NLWeb: {response.text if response else 'No response text'}"

    if error_message:
        print(f"Error calling NLWeb: {error_message}")
    
    return render_template('search_results.html', 
                           query=user_query, 
                           nlweb_response=nlweb_response_data, 
                           error_message=error_message)

if __name__ == '__main__':
    # current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # project_root_for_nlweb = current_file_dir 
    # os.environ["NLWEB_APP_PATH"] = project_root_for_nlweb
    # print(f"NLWEB_APP_PATH set to: {os.environ.get('NLWEB_APP_PATH')}")
    
    app.run(debug=True, port=5001)
