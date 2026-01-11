import google.generativeai as genai
import json
import time
import re
import random

def jitter():
    jitterTime = random.uniform(3, 5)  # Random time between 3 to 5 seconds
    print(f"Jittering for {jitterTime:.2f} seconds...")
    time.sleep(jitterTime)  # Random delay to mimic human behavior

# Setup API Key
genai.configure(api_key="AIzaSyDcLrjlrfChc-HwPgRpAzpxFz9F4PIP5nc")
# models = genai.list_models()
# print('Available Models:')
# models_list = []
# for m in models:
#     print(f"  - {m.display_name} (name: {m.name})")
#     models_list.append({
#         "display_name": m.display_name,
#         "name": m.name
#     })

# # Store models as JSON
# with open("available_models.json", "w") as f:
#     json.dump(models_list, f, indent=2)

model = genai.GenerativeModel('gemini-3-flash-preview')


def call_model_with_retries(prompt, max_retries=6, initial_backoff=1.0):
    """Call the LLM and handle rate-limit (429) errors with retry delays.

    The function will inspect exception messages for a suggested retry delay
    (e.g. 'Please retry in 54.61s' or 'retry_delay { seconds: 54 }') and honor
    that when present. Otherwise it uses exponential backoff.
    """
    backoff = initial_backoff
    for attempt in range(1, max_retries + 1):
        try:
            return model.generate_content(prompt)
        except Exception as e:
            text = str(e)
            # If the LLM/HTTP client includes a suggested retry delay, parse it
            m = re.search(r"Please retry in\s*(\d+(?:\.\d+)?)s", text)
            if not m:
                m = re.search(r"retry_delay\s*\{[^}]*seconds:\s*(\d+)\s*\}", text)

            if m:
                # Use the provided delay (add a small buffer)
                delay = float(m.group(1)) + 1.0
                print(f"Rate limit hit. Waiting {delay:.1f}s before retry (attempt {attempt}/{max_retries})")
                time.sleep(delay)
            else:
                # Fallback exponential backoff
                if attempt == max_retries:
                    print(f"Max retries reached ({max_retries}). Raising error.")
                    raise
                print(f"Transient error calling model: {e}. Backing off {backoff:.1f}s (attempt {attempt}/{max_retries})")
                time.sleep(backoff)
                backoff *= 2


def match_roles(resume_text, jobs_json):
    """this is a manual variable function to match roles using Gemini LLM"""
    results = []
    countdown =10
    try:
        for job in jobs_json:
            countdown -= 1
            if countdown <=0:
                print("Reached processing limit for this run.")
                break
            jitter()  # To avoid rate limiting
            print(f"Processing job: {job['role_name']} at {job['company']}")
            prompt = f"""
            Resume: {resume_text}
            ---
            Job Title: {job['role_name']}
            full_description: {job['full_description']}
            "years_exp_required": {job['years_exp_required']}
            Clearance: {job['clearance']}
            
            Analyze the match between this resume and the job. 
            Return ONLY a JSON object with:
            "score": (0-100),
            "fit_reason": (1 sentence),
            "missing_skills": [list]
            """
            
            try:
                response = call_model_with_retries(prompt)
                # Clean and parse the LLM's JSON response
                match_data = json.loads(response.text.replace('```json', '').replace('```', ''))
                
                # Combine original job data with LLM analysis
                job.update(match_data)
                results.append(job)
                
                # Rate limiting for free tier
                time.sleep(1) 
            except Exception as e:
                print(f"Error processing {job['role_name']}: {e}")
    except KeyboardInterrupt:
        pass
    return results

def generate_review_dashboard(jobs_json):
    with open("Match_Dashboard.md", "w") as f:
        f.write("# Job Match Dashboard\n\n")
        for job in jobs_json:
            # Create a URL-encoded prompt for manual use
            prompt_text = f"Review this job for me: {job['link']}"
            f.write(f"### {job['role_name']} - {job['company']}\n")
            f.write(f"* **Clearance:** {job['clearance']}\n")
            f.write(f"* [View Job Posting]({job['link']})\n")
            f.write(f"* [Chat with Gemini about this role](https://gemini.google.com/app?prompt={prompt_text})\n\n")




import json
import os
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from tqdm import tqdm

# Load your resume text from a file
# with open("my_resume.txt", "r", encoding="utf-8") as f:
#     resume_text = f.read()

from docx import Document

def extract_text_from_docx(file_path):
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        return "\n".join(full_text)
    except Exception as e:
        print(f"Error reading Word doc: {e}")
        return ""



def get_full_description(page, url):
    """Visits the link and pulls the deep-dive text."""
    try:
        page.goto(url, wait_until="domcontentloaded")
        # Target the specific container for full descriptions
        # Adjust selector if ClearanceJobs uses a different ID for full posts
        desc_element = page.locator(".job-description, #job-details-content")
        return desc_element.inner_text() if desc_element.is_visible() else ""
    except:
        return ""

def process_with_llm():
    with open('job_data_ClearanceJobs.json', 'r') as f:
        jobs = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        results = []
        # Process top 50 matches (to manage time/tokens)
        for job in tqdm(jobs[:50]): 
            # 1. Get the Deep Data
            full_text = get_full_description(page, job['link'])
            
            # 2. Construct the Prompt
            prompt = f"""
            RESUME:
            {resume_text}
            
            FULL JOB DESCRIPTION:
            {full_text if full_text else job['full_description']}
            
            Compare them. Return JSON: {{"score": 0-100, "reason": "...", "missing": []}}
            """
            
            # 3. Get AI Analysis
            response = call_model_with_retries(prompt)
            # (Add JSON parsing logic here)
            
            job['ai_match'] = response.text
            results.append(job)
            # Small delay to help avoid free-tier rate limits
            time.sleep(1)

        browser.close()
    return results

def create_nested_master_json(data_list, filename="llm_data_ClearenceJobs.json"):
    master_dict = {}

    for item in data_list:
        company = item['company']
        role = item['role_name']

        # If company isn't in dict, initialize it
        if company not in master_dict:
            master_dict[company] = {}

        # Nest the role details under the role_name key within that company
        master_dict[company][role] = {
            "score": item.get('score'),
            "fit_reason": item.get('fit_reason'),
            "missing_skills": item.get('missing_skills'),
            "location": item['location'],
            "link": item['link'],
            "date_posted": item['date_posted'],
            "clearance": item['clearance'],
            "polygraph": item['polygraph'],
            "full_description": item['full_description']
        }

    # Write to file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(master_dict, f, indent=4)
    
    return master_dict


####################################################
# Usage
resume_text = extract_text_from_docx("kristopher-moye-2482548.docx")
# print("Resume extracted. Length:", resume_text)
with open('job_data_ClearenceJobs.json', 'r') as f:
    jobs_json = json.load(f)
data_list = match_roles(resume_text, jobs_json)
    
create_nested_master_json(data_list)
