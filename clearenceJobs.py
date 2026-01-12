import json
from bs4 import BeautifulSoup
from icecream import ic
import requests
import time,random

def jitter():
    jitterTime = random.uniform(3, 5)  # Random time between 3 to 5 seconds
    print(f"Jittering for {jitterTime:.2f} seconds...",end='\r')
    time.sleep(jitterTime)  # Random delay to mimic human behavior

def get_total_pages():
    url = "https://www.clearancejobs.com/jobs?loc=5&received=31&ind=nq,nr,pg,nu,nv"
    headers = {"User-Agent": "Mozilla/5.0"} # Mimics a real browser
    # 1. Get the document behind the URL

    response = requests.get(url, headers=headers)
    html_content = response.text 

    # 2. Feed that document to Beautiful Soup
    soup = BeautifulSoup(html_content, 'html.parser')
    try:
        # Find the pagination container
        pagination = soup.select_one('.cj-pagination')
        if not pagination:
            return 1
        # Find all buttons and get the text of the last one before the "Next" arrow
        page_buttons = pagination.find_all('button', class_='btn')
        # Filter for buttons that contain only digits
        pages = [int(btn.get_text()) for btn in page_buttons if btn.get_text().isdigit()]
        print(f"Detected {max(pages) if pages else 1} pages to scrape.")
        return max(pages) if pages else 1
    except Exception:
        print(f"Detected {1} pages to scrape.")
        return 1

def parse_clearance_job_html(html_content):
    url = "https://www.clearancejobs.com/jobs?loc=5&received=31&ind=nq,nr,pg,nu,nv"
    headers = {"User-Agent": "Mozilla/5.0"} # Mimics a real browser
    # 1. Get the document behind the URL

    response = requests.get(url, headers=headers)
    html_content = response.text 

    # 2. Feed that document to Beautiful Soup
    soup = BeautifulSoup(html_content, 'html.parser')
    

    # Target the main container identified in your screenshot
    return  soup.select('div.job-search-list-item-desktop')

def get_full_job_details(url):
    """Fetches the full description from a standalone link."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        # 1. Fetch the page
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # 2. Parse the specific div
        soup = BeautifulSoup(response.text, 'html.parser')
        desc_node = soup.select_one(".job-description-text")
        
        return desc_node.get_text(separator="\n", strip=True) if desc_node else "Full text container not found."
    except Exception as e:
        return f"Error fetching details: {e}"
    
def scrape_full_description(page, url):
    """Navigates to the job link and pulls the deep-dive text."""
    try:
        page.goto(url, wait_until="domcontentloaded")
        # Explicitly wait for the class you identified
        page.wait_for_selector(".job-description-text", timeout=5000)
        full_description = page.locator(".job-description-text").inner_text()
        return full_description.strip()
    except Exception as e:
        print(f"  [!] Failed to deep-scrape {url}: {e}")
        return "Full description not found."

import re

def extract_salary(text):
    """Regex to find salary patterns like $118,600.00 - $178,000.00"""
    pattern = r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*-\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    match = re.search(pattern, text)
    if match:
        return {"min": match.group(1), "max": match.group(2)}
    return {"min": None, "max": None}

def process_scraped_data(job_cards):
    extracted_data = []
    
    for card in job_cards:
        number =job_cards.index(card)+1
        try:
            # 1. Role and Link (Drilling into the 'Header' and 'Job Name Wrapper')
            role_node = card.select_one('.job-search-list-item-desktop__job-name')
            role_name = role_node.get_text(strip=True)
            # Prepend base URL for the link
            role_link = "https://www.clearancejobs.com" + role_node['href']

            #1.5 Deep scraping for full description
            role_nameTruncate = role_name[:30]
            print(f"{number} |Deep scraping: {role_name}...")
            full_description = get_full_job_details( role_link)
            salary_data = extract_salary(full_description)
            # print(full_description)
            jitter()
            # 2. Company
            company_node = card.select_one('.job-search-list-item-desktop__company-name a')
            company = company_node.get_text(strip=True)

            # 3. Location (Handling the San Diego, CA On-Site structure)
            location_node = card.select_one('.cj-multiple-locations__location-name')
            location_text = location_node.get_text(strip=True) if location_node else "N/A"
            
            # setting_node = card.select_one('.cj-multiple-locations__type')
            # setting_text = setting_node.get_text(strip=True) if setting_node else ""

            # 4. Meta Data (Clearance, Date, Poly)
            # Since these use icon anchors, we'll find the specific group
            clearance = "Not Specified"
            poly = "Not Specified"
            posted = "Unknown"

            # In your HTML, these are often inside 'job-search-list-item-desktop__group'
            groups = card.find_all('div', class_='job-search-list-item-desktop__group')
            for group in groups:
                text = group.get_text(strip=True)
                # Simple logic: check for presence of specific icons or text patterns
                if group.find('i', class_='cjicon-locker'):
                    clearance = text
                elif group.find('i', class_='cjicon-polygraph'):
                    poly = text
                elif "Posted" in text:
                    posted = text

            # 5. Summary/Description
            desc_node = card.select_one('.job-search-list-item-desktop__description')
            description_preview = desc_node.get_text(strip=True) if desc_node else ""

            # Build the JSON object
            extracted_data.append({
                "role_name": role_name,
                "company": company,
                "link": role_link,
                "location": location_text,
                "date_posted": posted,
                "remote_eligible": "On-Site" if "(On-Site" in full_description else "Remote/Hybrid Search Needed",
                "salary": {
                    "raw": f"${salary_data['min']} - ${salary_data['max']}" if salary_data['min'] else "Not Listed",
                    "min_val": salary_data['min'],
                    "max_val": salary_data['max']
                },
                "travel_req": "10%" if "10% of the Time" in full_description else "Check Description",
                "clearance_required": clearance,
                "polygraph": poly,
                "years_exp_required": "8+" if "8 years" in full_description else "Not specified",
                "is_contingent": "Yes" if "contingent on program funding" in full_description.lower() else "No",
                "description_preview": description_preview,
                "full_description": full_description
            })

        except Exception as e:
            # If one card fails, print the error and continue to the next
            print(f"Error parsing card: {e}")
            continue

    return extracted_data
    
def finalize_to_json(data_list, filename="jobs_data.json"):
    cleaned_data = []
    
    for entry in data_list:
        # CLEANUP: Fixing the concatenated 'clearance' field
        # We extract 'Secret' or 'Top Secret' from the messy string
        raw_clearance = entry.get('clearance', '')
        actual_clearance = "Secret" if "Secret" in raw_clearance else "Not Specified"
        if "Top Secret" in raw_clearance: actual_clearance = "Top Secret"
        
        # CLEANUP: Extracting the real date if it was stuck in the clearance field
        date_val = "Posted today" if "today" in raw_clearance else entry.get('date_posted')
        clean_entry = {
            "role_name": entry['role_name'],
            "company": entry['company'],
            "link": entry['link'],
            "location": entry['location'],
            "date_posted": date_val,
            "clearance": actual_clearance,
            "travel_req": entry.get('travel_req', 'Check Description'),
            "remote_eligible": entry.get('remote_eligible', 'Remote/Hybrid Search Needed'),
            "salary": entry.get('salary', {'raw': 'Not Listed', 'min_val': None, 'max_val': None}),
            "polygraph": entry['polygraph'],
            "years_exp_required": entry.get('years_exp_required', 'Not specified'),
            "is_contingent": entry.get('is_contingent', 'No'),
            "full_description": entry['full_description']
            # "description_preview": entry['description_preview']
        }
        cleaned_data.append(clean_entry)

    # Convert List to JSON and write to file
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=4)
    
    return json.dumps(cleaned_data, indent=4) # Returns as a JSON string
# Example Usage with your provided snippet:
baseURL = "https://www.clearancejobs.com/jobs?loc=5&received=31&ind=nq,nr,pg,nu,nv"
total_pages = 3#get_total_pages()
all_jobs = []
for i in range(1,total_pages+1):  # Simulate multiple pages if needed
    currentURL = f"{baseURL}&PAGE={i}"
    print(f"Scraping Page {i} of {total_pages}: {currentURL}")
    jitter()  # Random delay before each request
    data = parse_clearance_job_html(baseURL)
    all_jobs.extend( process_scraped_data(data))
finalize_to_json(all_jobs, filename="job_data_ClearenceJobs.json")
print("Scraping complete. Data saved to job_data_ClearenceJobs.json")
print(f'total_jobs: {len(all_jobs)}')

