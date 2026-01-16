from pprint import pprint
import google.generativeai as genai
import re,time,random
import json,os
import google.generativeai as genai
from playwright.sync_api import sync_playwright
from tqdm import tqdm
from docx import Document

import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from common.helper import cprint


def jitter():
    jitterTime = random.uniform(3, 5)  # Random time between 3 to 5 seconds
    print(f"Jittering for {jitterTime:.2f} seconds...",end='\r')
    time.sleep(jitterTime)  # Random delay to mimic human behavior


def parse_salary(s):
    """Parse a salary value and return an integer amount in dollars.
    Handles ints, floats, and strings like "118,600.00" or "$118,600/yr".
    Returns 0 on failure.
    """
    import re
    try:
        if isinstance(s, int):
            return s
        if isinstance(s, float):
            return int(s)
        if isinstance(s, str):
            # Remove common non-numeric characters
            clean = s.replace(',', '').replace('$', '').strip()
            # Remove surrounding parentheses (they're not a negative indicator for salary)
            clean = clean.replace('(', '').replace(')', '')
            # Extract the first numeric token (handles '118600.00 per year')
            m = re.search(r"[-+]?\d+(?:\.\d+)?", clean)
            if m:
                return int(float(m.group(0)))
        return 0
    except Exception:
        return 0

# Setup API Key
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)
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

# model = genai.GenerativeModel('models/gemini-flash-lite-latest')
model = genai.GenerativeModel('models/gemini-3-flash-preview')


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
        print(len(jobs_json))
        for job in jobs_json:
            countdown -= 1
            if countdown <=0:
                print("Reached processing limit for this run.")
                break
            salary = parse_salary(job.get(['salary'].get('min_val', 0)))
            if salary < 105000:
                 print(f"  [!] Skipping {job['role_name']} at {job['company']} due to low salary: ${salary}")
                 continue
            # Normalize salary value on the job dict for downstream use
            job['salary_min'] = salary
            jitter()  # To avoid rate limiting
            print(f"Processing job: {job['role_name']} at {job['company']}")
            prompt = f"""
            Resume: {resume_text}
            ---
            Job Title: {job['role_name']}
            full_description: {job['full_description']}
            "years_exp_required": {job['years_exp_required']}
            Clearance: {job['clearance']}
            Salary: {salary} - {job['salary'].get('max_val', 'N/A')}
            
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

def chunk_list(data, chunk_size):
    """Break the list into batches of chunk_size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

def match_roles_batched(resume_text, jobs_json, batch_size=25):
    results = []
    
    # 1. Pre-filter by salary to save tokens/money
    # Normalize salary_min to integer for all jobs (handles strings like "118,600.00")
    for j in jobs_json:
        j['salary']['min_val'] = parse_salary(j['salary'].get('min_val', 0))
    print(len(jobs_json), "jobs loaded for batching.")
    filtered_jobs = [j for j in jobs_json if j['salary'].get('min_val', 0) >= 105000]
    print(f"Filtered jobs to {len(filtered_jobs)} with salary >= $105,000")

    for batch in chunk_list(filtered_jobs, batch_size):
        # Create a simplified version of the jobs for the prompt to save tokens
        job_summaries = []
        for j in batch:
            job_summaries.append({
                "id": j.get('link'), # Use link or UUID as a key
                "title": j.get('role_name'),
                "description": j.get('full_description'),
                "exp": j.get('years_exp_required'),
                "clearance": j.get('clearance')
            })

        prompt = f"""
        Resume: {resume_text}
        ---
        List of Jobs to Analyze:
        {json.dumps(job_summaries)}
        ---
        Task: Analyze the match between the resume and each job provided.
        Return a JSON list of objects. Each object MUST include the 'id' provided.
        
        Output Format:
        [
          {{
            "id": "original_id_here",
            "score": (0-100),
            "fit_reason": "one sentence explanation",
            "missing_skills": ["skill1", "skill2"]
          }}
        ]
        """

        try:
            print(f"Processing a batch of {len(batch)} jobs...")
            response = call_model_with_retries(prompt)
            
            # Use regex or json.loads to clean the response
            raw_text = response.text.replace('```json', '').replace('```', '').strip()
            batch_results = json.loads(raw_text)

            # Map results back to original data
            for match_item in batch_results:
                # Find the original job by ID to merge data
                original_job = next((item for item in batch if item['link'] == match_item['id']), None)
                if original_job:
                    original_job.update(match_item)
                    results.append(original_job)

            time.sleep(2) # Respect free tier rate limits
        except Exception as e:
            print(f"Error processing batch: {e}")
            
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





# Load your resume text from a file
# with open("my_resume.txt", "r", encoding="utf-8") as f:
#     resume_text = f.read()



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

def create_nested_master_json(data_list, filename=f"llm_data_ClearenceJobs.json"):
    master_dict = {}

    for item in data_list:
        company = item['company']
        role = item['role_name']

        # If company isn't in dict, initialize it
        if company not in master_dict:
            master_dict[company] = {}
        
        salary = parse_salary(item.get('salary', {}).get('min_val', 0))
        item['salary_min'] = salary
        if salary < 94000:
             print(f"  [!] Skipping {role} at {company} due to low salary: ${salary}")
             continue

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
resume_text = extract_text_from_docx("kristopher-moye-resume 2026_01_16.docx")
# print("Resume extracted. Length:", resume_text)
with open('JobData/ClearanceJobs/jobs_data.json', 'r') as f:
    jobs_json = json.load(f)
print(f"Loaded {len(jobs_json)} jobs from JSON.")
# Process the jobs in batches filled with qualifying jobs (salary >= 94k) to improve LLM efficiency
out_dir = 'JobData/ClearanceJobs/llmIn'
os.makedirs(out_dir, exist_ok=True)
chunk_size = 30  # target number of jobs per LLM batch
n = len(jobs_json)
idx = 0
batch_num = 1
import os
import json
import math

# ... (your previous imports and function defs) ...

resume_text = extract_text_from_docx("kristopher-moye-resume 2026_01_16.docx")
with open('JobData/ClearanceJobs/jobs_data.json', 'r') as f:
    jobs_json = json.load(f)

total_jobs = len(jobs_json)
print(f"Loaded {total_jobs} jobs from JSON.")

out_dir = 'JobData/ClearanceJobs/llmIn'
os.makedirs(out_dir, exist_ok=True)

chunk_size = 30 
idx = 0
batch_num = 1
qualifying_count = 0

while idx < total_jobs:
    batch = []
    batch_start = idx
    
    # Inner loop to fill the batch
    while idx < total_jobs and len(batch) < chunk_size:
        job = jobs_json[idx]
        salary_val = parse_salary(job.get('salary', {}).get('min_val', 0))
        
        if salary_val >= 105000:
            batch.append(job)
            qualifying_count += 1
        
        idx += 1
    
    if not batch:
        print("\n[!] No more qualifying jobs found in the remaining data.")
        break

    # --- PROGRESS CALCULATION ---
    percent_complete = (idx / total_jobs) * 100
    # Create a simple visual bar [##########----------]
    bar_length = 20
    filled = int(round(bar_length * idx / float(total_jobs)))
    bar = '█' * filled + '-' * (bar_length - filled)

    print(f"\n{'='*60}")
    print(f"BATCH {batch_num} | Progress: [{bar}] {percent_complete:.1f}%")
    print(f"Examining Index: {batch_start} to {idx-1}")
    print(f"Batch Size: {len(batch)} qualifying roles found so far")
    print(f"Total Qualified: {qualifying_count} / Total Scanned: {idx}")
    print(f"{'='*60}")

    try:
        # Pass the batch to the LLM
        data_list = match_roles_batched(resume_text, batch, batch_size=len(batch))
        
        out_path = os.path.join(out_dir, f"llm_data_ClearenceJobs_{batch_num}.json")
        create_nested_master_json(data_list, out_path)
        cprint(f"Successfully saved {out_path}", color="green")
        
    except Exception as e:
        cprint(f"Error processing batch {batch_num}: {e}", color="red")
        # Partial save logic here...

    batch_num += 1

print(f"\n✅ Finished. Total scanned: {idx}/{total_jobs}. Total qualified for LLM: {qualifying_count}")