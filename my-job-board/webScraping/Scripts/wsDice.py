from bs4 import BeautifulSoup
import requests,random,time,re
import  _init__
from common.helper import cprint 
import os,json

def jitter():
    jitterTime = random.uniform(0, 1)  # Random time between 0 to 2 seconds
    print(f"Jittering for {jitterTime:.2f} seconds...",end='\r')
    time.sleep(jitterTime)  # Random delay to mimic human behavior

def get_dice_links(url):
    # 1. Set a User-Agent to look like a real browser
    # Dice may block requests that look like basic Python scripts
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # 2. Use requests to get the actual HTML document
    print(f"Fetching: {url}")
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to retrieve page: Status {response.status_code}")
        return []

    # 3. Feed the CONTENT (response.text) to BeautifulSoup, not the URL
    soup = BeautifulSoup(response.text, 'html.parser')
    
    links = []
    # Target the data-testid you found earlier
    job_cards = soup.find_all('a', {'data-testid': 'job-search-job-card-link'})
    
    for card in job_cards:
        href = card.get('href')
        if href:
            links.append(href)
            
    return links

def get_total_pages(url):
    """
    Downloads the page and parses the pagination to find the total pages.
    """
    # 1. Setup headers to avoid bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    try:
        # 2. Perform the request inside the function
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the request was successful
        if not response.ok:
            print(f"❌ Failed to reach Dice. Status Code: {response.status_code}")
            return 1

        # 3. Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        # 4. Locate the pagination section
        # We look for <section aria-label="Page 1 of 25">
        pagination_sec = soup.find('section', {'aria-label': lambda x: x and 'Page' in x and 'of' in x})
        
        if pagination_sec:
            spans = pagination_sec.find_all('span')
            if spans:
                try:
                    # The total number is the text in the very last <span>
                    total_pages = int(spans[-1].get_text(strip=True))
                    return total_pages
                except (ValueError, IndexError):
                    print("⚠️ Could not convert page count to integer.")
        
        print("ℹ️ Pagination section not found. Defaulting to 1 page.")
        return 1

    except requests.exceptions.RequestException as e:
        print(f"❌ Network error occurred: {e}")
        return 1

def extract_salary(text):
    """Parse salary from text and return integer min/max in dollars.

    Returns dict with integer values or 0 when not found.
    Examples handled:
      - "$118,600.00 - $178,000.00" => {"min": 118600, "max": 178000}
      - "$118,600" => {"min": 118600, "max": 118600}
      - no match => {"min": 0, "max": 0}
    """
    def to_int(num_str: str) -> int:
        try:
            # remove commas and cast through float to handle decimals
            return int(float(num_str.replace(',', '')))
        except Exception:
            return 0

    # Range pattern
    range_pattern = r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*-\s*\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    m = re.search(range_pattern, text) 

    if m:
        return {"min": to_int(m.group(1)), "max": to_int(m.group(2))}

    # Single value pattern
    single_pattern = r"\$(\d{1,3}(?:,\d{3})*(?:\.\d+)?)"
    m = re.search(single_pattern, text)
    if m:
        val = to_int(m.group(1))
        return {"min": val, "max": val}

    return {"min": 0, "max": 0}

# def parse_dice_job_html(url: str):
#     """Fetch the search results page and return job card elements."""
#     headers = {
#         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
#     }
#     try:
#         response = requests.get(url, headers=headers, timeout=10)
#         response.raise_for_status()
#         soup = BeautifulSoup(response.text, 'html.parser')
#         # Dice job cards are usually wrapped in this ID or similar div structures
#         return soup.find_all('d-job-card') or soup.select('div.card')
#     except Exception as e:
#         cprint(f"Warning: failed to fetch {url}: {e}", color='red')
#         return []

def get_full_job_details(url):
    """
    Fetches the skills list and the full description text from a Dice job page.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Extract Skills (The InfoBadges)
        skills = []
        skill_nodes = soup.select(".SeuiInfoBadge div")
        if skill_nodes:
            skills = [s.get_text(strip=True) for s in skill_nodes]
        
        skills_str = "Skills: " + ", ".join(skills) if skills else ""

        # 2. Extract Description Summary
        # Note: Dice uses a dynamic class that starts with 'job-detail-description-module'
        desc_node = soup.find("div", class_=lambda x: x and 'jobDescription' in x)
        
        # Fallback if the specific class above fails
        if not desc_node:
            desc_node = soup.find(id="jobDescription") or soup.select_one(".job-details-body")

        full_text = desc_node.get_text(separator="\n", strip=True) if desc_node else ""

        # 3. Combine them for a complete picture
        print(f'Skills: {skills}')
        print(f'full_text: {full_text}')
        combined_content = f"{skills_str}\n\n{full_text}"
        
        return combined_content if combined_content.strip() else "Full text container not found."

    except Exception as e:
        return f"Error fetching details: {e}"
    
import re

import re

def expand_job_details(full_text, base_info=None):
    """
    Parses the massive text block from Dice to extract structured ATS data.
    """
    # 1. Extract Years of Experience (Targeting "18 or more years")
    # This regex looks for a number followed by 'or more years' or 'years'
    years_match = re.search(r'(\d+)\s*(?:\+|or more)?\s*years', full_text, re.IGNORECASE)
    years_exp = int(years_match.group(1)) if years_match else 0

    # 2. Extract Clearance Levels (TS/SCI vs Poly)
    clearance = "Not Specified"
    if "TS/SCI" in full_text:
        clearance = "TS/SCI"
    elif "Top Secret" in full_text:
        clearance = "Top Secret"
        
    has_poly = "Yes" if "Polygraph" in full_text else "No"

    # 3. Extract Salary (Targeting: Target salary range: $200,001 - $240,000)
    salary_pattern = r'Target salary range:\s*\$(\d{1,3}(?:,\d{3})*)\s*-\s*\$(\d{1,3}(?:,\d{3})*)'
    salary_match = re.search(salary_pattern, full_text)
    
    salary_dict = {"min": 0, "max": 0}
    if salary_match:
        salary_dict["min"] = int(salary_match.group(1).replace(',', ''))
        salary_dict["max"] = int(salary_match.group(2).replace(',', ''))

    # 4. Build the final dictionary
    return {
        "role_name": base_info.get("role_name") if base_info else "Unknown",
        "company": base_info.get("company") if base_info else "Unknown",
        "link": base_info.get("link") if base_info else "N/A",
        "requirements": {
            "years_exp": years_exp,
            "clearance": clearance,
            "polygraph": has_poly,
            "remote": "No" if "Potential for Remote Work: No" in full_text else "Yes/Hybrid"
        },
        "compensation": salary_dict,
        "raw_description": full_text
    }

def expand_job_details_(base_data):
    """
    Takes the basic scraped data and deep-parses the full_description 
    to extract specific ATS-critical fields.
    """
    print(base_data)
    desc = base_data["full_description"]
    
    # 1. Extract Years of Experience (e.g., "18 or more years", "5+ years")
    # Searches for a number followed by "years" or "yr"
    years_match = re.search(r'(\d+)\s*(?:\+|or more)?\s*years?', desc, re.IGNORECASE)
    years_exp = int(years_match.group(1)) if years_match else 0

    # 2. Extract Clearance Requirements
    # Specifically looking for the common Defense tiers
    clearance_map = {
        "TS/SCI": r"TS/SCI|Top Secret/SCI|Top Secret.*Sensitive",
        "Top Secret": r"Top Secret|(?<!SCI )TS(?!/SCI)",
        "Secret": r"Secret",
        "Polygraph": r"Polygraph|CI Poly|Full Scope Poly"
    }
    
    found_clearance = "None Listed"
    for level, pattern in clearance_map.items():
        if re.search(pattern, desc, re.IGNORECASE):
            found_clearance = level
            break

    # 3. Extract Education
    education = "Not Specified"
    if re.search(r"Bachelor's|BS|BA|Degree", desc, re.IGNORECASE):
        education = "Bachelor's"
    if re.search(r"Master's|MS|MA|MBA", desc, re.IGNORECASE):
        education = "Master's"

    # 4. Clean the "Skills" from the top of the description
    # This grabs the "Skills: ..." line we built in the previous step
    skills_match = re.search(r"Skills: (.*?)\n", desc)
    skills_list = [s.strip() for s in skills_match.group(1).split(',')] if skills_match else []

    # 5. Build the Final JSON Dictionary
    return {
        "role_name": base_data["role_name"],
        "company": base_data["company"],
        "link": base_data["link"],
        "location": base_data["location"],
        "date_posted": base_data["date_posted"],
        "requirements": {
            "years_exp": years_exp,
            "clearance": found_clearance,
            "education": education,
            "polygraph_required": "Yes" if "Polygraph" in desc else "No"
        },
        "salary": base_data["salary"],
        "skills_keywords": skills_list,
        "is_remote": "No" if "Potential for Remote Work: No" in desc else "Check Description",
        "job_id": re.search(r"Position Id:\s*(\d+)", desc).group(1) if "Position Id:" in desc else "N/A"
    }

# --- Execution ---
# search_url = "https://www.dice.com/jobs?filters.employmentType=FULLTIME&location=California%2C+USA"

###################################
search_url =  "https://www.dice.com/jobs?filters.employmentType=FULLTIME&filters.workplaceTypes=On-Site&location=California%2C+USA&latitude=36.778261&longitude=-119.4179324&countryCode=US&locationPrecision=State&adminDistrictCode=CA"
# search_url = "https://www.dice.com/jobs?filters.employmentType=FULLTIME&location=California%2C+USA"


# --- Usage ---
totalPages = get_total_pages(search_url)
job_links = get_dice_links(search_url)
for jobURL in job_links:
    expand_job_details(get_full_job_details(jobURL))
    print('%--------------------')
    break
# print(locals())
# print(f"Found {len(job_links)} jobs.")
# print(job_links)

if __name__ =="__main__":
    # 1. Setup the directory
    output_dir = "JobData/ClearanceJobs/"
    os.makedirs(output_dir, exist_ok=True)


    all_extracted_jobs = []
    seen_links = set()

    # 2. Start the Pagination Loop
    cprint(f"🚀 Starting scrape. Total pages to scan: {totalPages}", color='cyan')

    for page_num in range(1, totalPages + 1):
        # Construct the paginated URL
        current_url = f"{search_url}&page={page_num}"
        cprint(f"[+] Scraping Page {page_num}: {current_url}", color='green')
        job_links = get_dice_links(search_url)
        # Get the job cards for the current page
        job_cards = expand_job_details(get_full_job_details(jobURL))
        
        if not job_cards:
            cprint(f"  [!] No job cards found on page {page_num}. Ending.", color='yellow')
            break

        # 3. Process each job card
        for idx, card in enumerate(job_cards, start=1):
            # Extract the basic info and the link
            link_node = card.select_one('a[data-testid="job-search-job-card-link"]')
            if not link_node: continue
            
            role_link = link_node.get('href')
            if not role_link or role_link in seen_links: continue
            
            # Deep scrape the description
            role_name = link_node.get_text(strip=True)
            cprint(f"  ({idx}) Processing: {role_name[:40]}...", color='blue')
            
            raw_description = get_full_job_details(role_link)
            
            # Build the base object
            base_data = {
                "role_name": role_name,
                "company": card.select_one('a[data-testid="search-result-item-company-name"]').get_text(strip=True) if card.select_one('a[data-testid="search-result-item-company-name"]') else "Unknown",
                "link": role_link,
                "location": card.select_one('span[data-testid="search-result-item-location"]').get_text(strip=True) if card.select_one('span[data-testid="search-result-item-location"]') else "N/A",
                "date_posted": "Unknown", # Can be pulled from the card logic
                "salary": extract_salary(raw_description),
                "full_description": raw_description
            }

            # 4. Expand into the ATS-ready dictionary
            final_job = expand_job_details(base_data)
            all_extracted_jobs.append(final_job)
            seen_links.add(role_link)

            # Respectful scraping: Jitter between deep scrapes
            time.sleep(random.uniform(1.5, 3.0))

        cprint(f"--- Finished Page {page_num} | Total Jobs: {len(all_extracted_jobs)} ---", color='yellow')

    # 5. Save to JSON
    filename = f"{output_dir}Dice_Scrape_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_extracted_jobs, f, indent=4)

    cprint(f"🎉 SUCCESS! Saved {len(all_extracted_jobs)} jobs to {filename}", color='green')