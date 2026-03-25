from pprint import pprint
import re,time,random
import json,os
import google.generativeai as genai
# from playwright.sync_api import sync_playwright
# from tqdm import tqdm
from docx import Document
from profileSettings import *
import argparse, sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from common.helper import cprint

# from openai import AzureOpenAI
# client = AzureOpenAI(
#     api_key=os.getenv("AZURE_OPENAI_KEY"),
#     api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
#     azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT")
# )




def jitter():
    jitterTime = random.uniform(3, 5)  # Random time between 3 to 5 seconds
    print(f"Jittering for {jitterTime:.2f} seconds...",end='\r')
    time.sleep(jitterTime)  # Random delay to mimic human behavior

# Setup API Key
api_key = os.getenv("GENAI_API_KEY")
genai.configure(api_key=api_key)

def get_model_selection():
    """
    Lists Gemini models sorted by Free Tier availability first, 
    then Paid-only models.
    """
    try:
        raw_models = genai.list_models()
        
        # Define known "Paid Only" models based on 2026 status
        # Note: gemini-3-pro and specialized 'image' variants usually require billing.
        paid_keywords = ["-3-pro", "image", "ultra", "vision"]
        
        free_tier = []
        paid_tier = []

        for m in raw_models:
            if 'generateContent' in m.supported_generation_methods:
                model_data = {"display_name": m.display_name, "name": m.name}
                
                # Sort logic: check if name contains any paid keywords
                if any(key in m.name.lower() for key in paid_keywords):
                    paid_tier.append(model_data)
                else:
                    free_tier.append(model_data)

        # Combine lists: Free first, then Paid
        all_selectable = free_tier + paid_tier
        
        print("\n--- Available Gemini Models ---")
        print(f"{'#':<3} {'Model Name':<30} {'Tier Access'}")
        print("-" * 50)

        for i, m in enumerate(all_selectable, 1):
            # Labeling the tier for clarity
            is_free = i <= len(free_tier)
            tier_label = "[FREE TIER]" if is_free else "[PAID ONLY]"
            
            # Highlight Flash-Lite or Flash as recommended for your scraper
            rec = " ⭐" if "flash" in m['display_name'].lower() and is_free else ""
            
            print(f"{i:<3} {m['display_name']:<30} {tier_label}{rec}")

        # User Input Logic
        while True:
            try:
                msg = f"\nSelect model (1-{len(all_selectable)}) [Default: 1]: "
                choice = input(msg).strip()
                
                if choice == "":
                    selected = all_selectable[0]
                    break
                    
                idx = int(choice)
                if 1 <= idx <= len(all_selectable):
                    selected = all_selectable[idx - 1]
                    break
                print("Out of range.")
            except ValueError:
                print("Enter a valid number.")

        print(f"✅ Active Model: {selected['display_name']}")
        return selected['name']

    except Exception as e:
        print(f"❌ Error: {e}")
        return None
# --- Example Usage ---
# MODEL_ID = get_model_selection()
# model = genai.GenerativeModel(MODEL_ID)

# # Store models as JSON
# with open("available_models.json", "w") as f:
#     json.dump(models_list, f, indent=2)

model = genai.GenerativeModel(llmModel)
# model = genai.GenerativeModel('models/gemini-3-flash-preview')

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

import time
import re
from openai import AzureOpenAI

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_key="YOUR_AZURE_OPENAI_KEY",
    api_version="2024-02-01",
    azure_endpoint="https://YOUR-RESOURCE-NAME.openai.azure.com"
)

def call_Azure_with_retries(prompt, max_retries=2, initial_backoff=1.0):
    """
    Azure OpenAI equivalent of the Gemini retry wrapper.
    Handles 429 rate limits, parses retry-after hints, and falls back to exponential backoff.
    """
    backoff = initial_backoff

    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4o",   # or your deployed model name
                messages=[{"role": "user", "content": prompt}]
            )
            return response

        except Exception as e:
            text = str(e)

            # Azure sometimes returns: "Please retry after 20 seconds"
            m = re.search(r"retry after\s*(\d+)", text, re.IGNORECASE)

            # Or: "Retry-After: 15"
            if not m:
                m = re.search(r"Retry-After:\s*(\d+)", text, re.IGNORECASE)

            if m:
                delay = float(m.group(1)) + 1.0
                print(f"Rate limit hit. Waiting {delay:.1f}s before retry (attempt {attempt}/{max_retries})")
                time.sleep(delay)
                continue

            # Fallback exponential backoff
            if attempt == max_retries:
                print(f"Max retries reached ({max_retries}). Raising error.")
                raise

            print(f"Transient error calling Azure OpenAI: {e}. Backing off {backoff:.1f}s (attempt {attempt}/{max_retries})")
            time.sleep(backoff)
            backoff *= 2

def call_Gemini_with_retries(prompt, max_retries=2, initial_backoff=1.0):
    """Call the LLM and handle rate-limit (429) errors with retry delays.

    The function will inspect exception messages for a suggested retry delay
    (e.g. 'Please retry in 54.61s' or 'retry_delay { seconds: 54 }') and honor
    that when present. Otherwise it uses exponential backoff.
    """
    model = genai.GenerativeModel('models/gemini-flash-lite-latest')
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
                try:
                    delay = float(m.group(1)) + 1.0
                    print(f"Rate limit hit. Waiting {delay:.1f}s before retry (attempt {attempt}/{max_retries})")
                    time.sleep(delay)
                except KeyboardInterrupt:
                    pass
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
            if salary < minSalary:
                 print(f"  [!] Skipping {job['role_name']} at {job['company']} due to low salary: ${salary}")
                 continue
            # Normalize salary value on the job dict for downstream use
            job['salary_min'] = salary
            jitter()  # To avoid rate limiting
            print(f"Processing job: {job['role_name']} at {job['company']}")
            # Analyze the match between this resume and the job. 
            prompt = f"""
                Resume Content: {resume_text}

                Analyze the match for the following Job:
                - Title: {job['role_name']}
                - Required Experience: {job['years_exp_required']} years
                - Required Clearance: {job['clearance']}
                - Description: {job['full_description']}

                CRITICAL LOGIC RULES:
                1. YEARS OF EXPERIENCE: Treat this as a 'minimum threshold.' If the resume shows MORE years (e.g., 10) than the job requires (e.g., 8), it is a PERFECT MATCH. Only penalize if resume < required.
                2. CLEARANCE MATCHING: 
                - 'Top Secret/SCI' matches and exceeds 'Top Secret'. 
                - 'Top Secret' matches and exceeds 'Secret'.
                - If the resume states an active clearance that meets or exceeds the job requirement, it is a 100% match for that criteria.
                3. SCORING: Weight the score heavily on Technical Skills, Years of Experience, and Clearance.

                Return ONLY a JSON object:
                {{
                "score": (0-100),
                "fit_reason": "One concise sentence explaining the match based on the rules above.",
                "missing_skills": ["List only skills/certs explicitly missing from the resume"]
                "matching_skills":["List only skills/certs explicitly present from the resume"]
                }}
                """
            
            try:
                response = call_Gemini_with_retries(prompt)
                # Ensure we received a response object with text
                if not response or not hasattr(response, 'text') or response.text is None:
                    print(f"⚠️ Warning: No response from LLM for job '{job.get('role_name')}'. Skipping.")
                    continue

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
    filtered_jobs = [j for j in jobs_json if j['salary'].get('min_val', 0) >= minSalary]
    print(f"Filtered jobs to {len(filtered_jobs)} with salary >= ${minSalary}.")

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
        
        CRITICAL LOGIC RULES:
            1. YEARS OF EXPERIENCE: Treat this as a 'minimum threshold.' If the resume shows MORE years (e.g., 10) than the job requires (e.g., 8), it is a PERFECT MATCH. Only penalize if resume < required.
            2. CLEARANCE MATCHING: 
            - 'Top Secret/SCI' matches and exceeds 'Top Secret'. 
            - 'Top Secret' matches and exceeds 'Secret'.
            - If the resume states an active clearance that meets or exceeds the job requirement, it is a 100% match for that criteria.
            3. SCORING: Weight the score heavily on Technical Skills, Years of Experience, and Clearance.
            
            Before scoring, classify each job into one primary domain category:
            ["Cybersecurity", "Systems Engineering", "Software Development", 
            "Program/Project Management", "Intelligence", "Logistics", 
            "Administrative", "Writing/Documentation", "Other"].

            Also classify the resume into its top 1-2 domain categories.

            Apply a domain alignment adjustment:
            - If job domain matches resume domain → no penalty.
            - If job domain is adjacent → subtract 5 points.
            - If job domain is unrelated → subtract 20 points.

        Output Format:
            [
                {{
                "id": "original_id_here",
                "score": <integer between 0-100>,
                "fit_reason": "One concise sentence explaining the match based on the rules above.",
                "missing_skills": ["List only skills/certs explicitly missing from the resume"],
                "matching_skills": ["List only skills/certs explicitly present from the resume"]
                }}
            ]
        """

        # Task: Analyze the match between the resume and each job provided.
        # Return a JSON list of objects. Each object MUST include the 'id' provided.
        
        # Output Format:
        # [
        #   {{
        #     "id": "original_id_here",
        #     "score": <integer between 0-100>,
        #     "fit_reason": "one sentence explanation",
        #     "missing_skills": ["skill1", "skill2"]
        #   }}
        # ]

        try:
            print(f"Processing a batch of {len(batch)} jobs...")
            response = call_Gemini_with_retries(prompt)

            # Ensure response is valid
            if not response or not hasattr(response, 'text') or response.text is None:
                print("⚠️ Warning: No response from LLM for batch, skipping this batch.")
                continue

            # Use regex or json.loads to clean the response
            raw_text = response.text.replace('```json', '').replace('```', '').strip()

            # Extract JSON portion if there is surrounding text
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', raw_text)
            if json_match:
                raw_text = json_match.group()
            else:
                print(f"⚠️ Warning: No JSON found in LLM response (preview): {raw_text[:200]}")
                continue

            batch_results = json.loads(raw_text)

            # Map results back to original data
            for match_item in batch_results:
                # Find the original job by ID to merge data
                original_job = next((item for item in batch if item['link'] == match_item['id']), None)
                if original_job:
                    original_job.update(match_item)
                    results.append(original_job)

            time.sleep(2) # Respect free tier rate limits
        except ConnectionError as e:
            print(f"Error processing batch: {e}")
            
    return results

def match_roles_batched(resume_text, jobs_json, batch_size=25):
    results = []
    
    # --- NEW: Load the Tracking Data ---
    # Path assumes server.py and this script can both see the same applied_jobs.json
    tracker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'applied_jobs.json'))
    applied_ids = []
    if os.path.exists(tracker_path):
        with open(tracker_path, 'r') as f:
            applied_ids = json.load(f)

    # 1. Pre-filter by Salary AND Applied Status
    for j in jobs_json:
        j['salary']['min_val'] = parse_salary(j['salary'].get('min_val', 0))
    
    # The "Wild" Filter: Must meet salary AND must NOT be in applied_ids
    filtered_jobs = [
        j for j in jobs_json 
        if j['salary'].get('min_val', 0) >= minSalary 
        and j.get('jobId') not in applied_ids  # Skip what we've already done
    ]
    
    print(f"Total jobs: {len(jobs_json)} | Filtered (Salary/Applied) down to: {len(filtered_jobs)}.")

    # 2. Proceed with Chunking (unchanged, but now much faster)
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
        
        CRITICAL LOGIC RULES:
            1. YEARS OF EXPERIENCE: Treat this as a 'minimum threshold.' If the resume shows MORE years (e.g., 10) than the job requires (e.g., 8), it is a PERFECT MATCH. Only penalize if resume < required.
            2. CLEARANCE MATCHING: 
            - 'Top Secret/SCI' matches and exceeds 'Top Secret'. 
            - 'Top Secret' matches and exceeds 'Secret'.
            - If the resume states an active clearance that meets or exceeds the job requirement, it is a 100% match for that criteria.
            3. SCORING: Weight the score heavily on Technical Skills, Years of Experience, and Clearance.

        Output Format:
            [
                {{
                "id": "original_id_here",
                "score": <integer between 0-100>,
                "fit_reason": "One concise sentence explaining the match based on the rules above.",
                "missing_skills": ["List only skills/certs explicitly missing from the resume"],
                "matching_skills": ["List only skills/certs explicitly present from the resume"]
                }}
            ]
        """

        # Task: Analyze the match between the resume and each job provided.
        # Return a JSON list of objects. Each object MUST include the 'id' provided.
        
        # Output Format:
        # [
        #   {{
        #     "id": "original_id_here",
        #     "score": (0-100),
        #     "fit_reason": "one sentence explanation",
        #     "missing_skills": ["skill1", "skill2"]
        #   }}
        # ]

        try:
            print(f"Processing a batch of {len(batch)} jobs...")
            response = call_Gemini_with_retries(prompt)

            # Ensure response is valid
            if not response or not hasattr(response, 'text') or response.text is None:
                print("⚠️ Warning: No response from LLM for batch, skipping this batch.")
                continue

            # Use regex or json.loads to clean the response
            raw_text = response.text.replace('```json', '').replace('```', '').strip()
            
            # Extract just the JSON portion (handles extra text before/after)
            json_match = re.search(r'\[[\s\S]*\]|\{[\s\S]*\}', raw_text)
            if json_match:
                raw_text = json_match.group()
            else:
                # If no valid JSON structure found, log and skip this batch
                print(f"⚠️ Warning: No valid JSON found in response. Raw response: {raw_text[:200]}")
                continue
            
            if not raw_text.strip():
                print(f"⚠️ Warning: Empty JSON response, skipping batch")
                continue
            
            try:
                batch_results = json.loads(raw_text)
            except json.JSONDecodeError as e:
                print(f"⚠️ Warning: Failed to parse JSON: {e}")
                print(f"Raw text: {raw_text[:300]}")
                continue

            # Map results back to original data
            for match_item in batch_results:
                original_job = next((item for item in batch if item['link'] == match_item['id']), None)
                if original_job:
                    original_job.update(match_item)
                    results.append(original_job)

                    # --- THE TAILORING TRIGGER ---
                    score = original_job.get('score', 0)
                    if isinstance(score, (int, float)) and score >= minScore:
                        print(f"🔥 High Match Found ({score}%). Triggering Tailor script...")
                        # Here you would call your tailoring function
                        # generate_tailored_resume(resume_text, original_job

            time.sleep(2) # Respect free tier rate limits
        except ConnectionError as e:
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
        if salary < minSalary:
             print(f"  [!] Skipping {role} at {company} due to low salary: ${salary}")
             continue

        # Nest the role details under the role_name key within that company
        master_dict[company][role] = {
            "date_sourced": time.strftime("%Y-%m-%d"),
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

def update_grand_master(grand_master, batch_data):
    """
    Merges batch_data into grand_master using the 
    {Company: {Role: {Details}}} structure.
    """
    for item in batch_data:
        company = item.get('company', 'Unknown Company')
        role = item.get('role_name', 'Unknown Role')

        if company not in grand_master:
            grand_master[company] = {}

        # Map the item to the specific nested structure
        grand_master[company][role] = {
            "date_sourced": time.strftime("%Y-%m-%d"),
            "score": item.get('score'),
            "fit_reason": item.get('fit_reason'),
            "missing_skills": item.get('missing_skills', []),
            "location": item.get('location', 'N/A'),
            "link": item.get('link', '#'),
            "date_posted": item.get('date_posted', 'Unknown'),
            "clearance": item.get('clearance', 'Not Specified'),
            "polygraph": item.get('polygraph', 'Not Specified'),
            "full_description": item.get('full_description', '')
        }
    return grand_master



def main(selected_resume):
    import os,json
    import json
    # 4. Extract text from the chosen file
    print(f"✅ Selected: {selected_resume}")

    # Resolve resume path to the deployment's Resume_Uploads directory when necessary.
    candidates = []
    # If user provided an absolute path, try it first
    if os.path.isabs(selected_resume):
        candidates.append(selected_resume)
    else:
        # If given just a filename, try relative to working dir, script dir, and webScraping/Resume_Uploads
        candidates.append(os.path.join(os.getcwd(), selected_resume))
        candidates.append(os.path.join(current_dir, selected_resume))
        candidates.append(os.path.join(current_dir, 'Resume_Uploads', selected_resume))
        candidates.append(os.path.join(parent_dir, 'Resume_Uploads', selected_resume))

    # Also handle cases where selected_resume accidentally contains 'Scripts\\Resume_Uploads' path
    if 'Scripts' + os.sep + 'Resume_Uploads' in str(selected_resume):
        bn = os.path.basename(selected_resume)
        candidates.insert(0, os.path.join(parent_dir, 'Resume_Uploads', bn))

    resume_path = None
    for p in candidates:
        try:
            if p and os.path.exists(p):
                resume_path = p
                break
        except Exception:
            continue

    if resume_path is None:
        # Fallback: pass selected_resume through (existing behavior)
        resume_path = selected_resume

    print(f"DEBUG: Using resume path: {resume_path}")
    resume_text = extract_text_from_docx(resume_path)
    print(f"Scan Settings: {minSalary} salary, {minScore} score minimum")

    # Resolve paths
    jobs_data_path = resolve_path(webscraped_jobs_path, webscraped_jobs_path_ABS)
    out_dir = resolve_path('JobData/DiceJobs', ws_data_path_In_ABS)
    os.makedirs(out_dir, exist_ok=True)
    master_file_path = os.path.join(out_dir, "ATS_MASTER_ANALYSIS.json")

    # --- LAYER 1: LOAD EXISTING PROGRESS ---
    grand_master_dict = {}
    if os.path.exists(master_file_path):
        with open(master_file_path, 'r', encoding='utf-8') as f:
            try:
                grand_master_dict = json.load(f)
                cprint(f"🔄 Resuming session: {len(grand_master_dict)} companies already analyzed.", color="yellow")
            except json.JSONDecodeError:
                grand_master_dict = {}

    with open(jobs_data_path, 'r') as f:
        jobs_json = json.load(f)
    
    total_jobs = len(jobs_json)
    idx, batch_num, qualifying_count = 0, 1, 0

    while idx < total_jobs:
        batch = []
        batch_start = idx
        
        while idx < total_jobs and len(batch) < atsBatchSize:
            job = jobs_json[idx]
            role_name = job.get('role_name')
            company = job.get('company')
            salary_val = parse_salary(job.get('salary', {}).get('min_val', 0))
            
            # --- LAYER 2: SKIP ANALYZED JOBS ---
            # Check if this specific role at this company is already in our ATS_MASTER_ANALYSIS
            if company in grand_master_dict and role_name in grand_master_dict[company]:
                # Log occasionally so the console isn't flooded
                if idx % 10 == 0:
                    print(f"⏭️ Skipping {role_name} (Already analyzed)")
            elif salary_val >= minSalary:
                batch.append(job)
                qualifying_count += 1
            
            idx += 1
        
        if not batch:
            if idx >= total_jobs: break
            continue # Keep looking for new qualifying jobs

        # # --- PROGRESS UI ---
        # percent_complete = (idx / total_jobs) * 100
        # print(f"\nBATCH {batch_num} | Processing {len(batch)} NEW roles | Progress: {percent_complete:.1f}%")
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
            # Call LLM
            data_list = match_roles_batched(resume_text, batch, batch_size=len(batch))
            
            # Update internal dict
            grand_master_dict = update_grand_master(grand_master_dict, data_list)

            # --- LAYER 3: IMMEDIATE SAVE (Write-Through) ---
            # Even if the next batch crashes, this one is safe on disk
            with open(master_file_path, 'w', encoding='utf-8') as f:
                json.dump(grand_master_dict, f, indent=4)
            
            cprint(f"✅ Progress checkpoint saved to ATS_MASTER_ANALYSIS.json", color="green")
            
        except Exception as e:
            cprint(f"❌ Rate limit or Error on batch {batch_num}: {e}", color="red")
            # Break the loop but the final save is already done
            break

        # batch_num += 1
        # out_path = os.path.join(f'{out_dir}\\llmIn', f"llm_data_ClearenceJobs_{batch_num}.json")
        # # create_nested_master_json(data_list, out_path)
        # cprint(f"Successfully saved {out_path}", color="green")

    print(f"\n✅ Session Ended. Total analyzed: {len(grand_master_dict)} roles.")

def resumeFromUI():
    # 1. Initialize the Argument Parser
    parser = argparse.ArgumentParser(description="ClearanceJobs Scraper and Analyzer")

    # 2. Define the inputs the UI is sending
    # parser.add_argument("--resume_path", type=str, required=True, help="Path to the user's resume")
    # parser.add_argument("--link", type=str, required=True, help="URL of the job posting")

    parser.add_argument("--resume_path", type=str, required=True, help="resume used for analysis")
    parser.add_argument("--model", type=str, required=True, help="LLM model used for analysis")
    # parser.add_argument("--model", type=str, required=True, help="Gemini model ID to use")

    args = parser.parse_args()

    # 3. Use the data in your script
    print(f"--- Starting Analysis Pipeline ---")
    print(f"LLM Model: {args.model}")
    return args.resume_path
####################################################
# Usage
main(resumeFromUI())
# if __name__ == "__main__":

#     import os
#     # 1. Get list of docx files
#     my_job_uploads_dir = os.path.join(os.path.dirname(__file__), "Resume_Uploads")
#     docx_files = [f for f in os.listdir(my_job_uploads_dir) if f.endswith('.docx')]

#     if not docx_files:
#         print("❌ No .docx files found in the Resume_Uploads directory.")
#         exit()

#     # 2. Display the list to the user
#     print("\n--- Available Resumes ---")
#     for i, filename in enumerate(docx_files, 1):
#         print(f"{i}. {filename}")

#     # 3. Handle selection
#     while True:
#         try:
#             choice = int(input(f"\nSelect a resume by number (1-{len(docx_files)}): "))
#             if 1 <= choice <= len(docx_files):
#                 selected_resume = docx_files[choice - 1]
#                 break
#             else:
#                 print(f"Please enter a number between 1 and {len(docx_files)}.")
#         except ValueError:
#             print("Invalid input. Please enter a number.")
#     main(selected_resume)