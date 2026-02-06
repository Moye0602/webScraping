from bs4 import BeautifulSoup
import requests,random,time,re
import  _init__
from common.helper import cprint 
import os,json
import re
from pprint import pprint

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
    salary_dict = {"min": 0, "max": 0}
    
    # This regex looks for:
    # 1. A dollar sign \$
    # 2. A number with commas (\d{1,3}(?:,\d{3})*)
    # 3. A separator ( - or to )
    # 4. The second dollar sign and number
    pattern = r"\$(\d{1,3}(?:,\d{3})*)\s*[-–—]\s*\$(\d{1,3}(?:,\d{3})*)"
    
    match = re.search(pattern, text)
    
    if match:
        # We remove the commas before converting to int
        salary_dict["min"] = int(match.group(1).replace(',', ''))
        salary_dict["max"] = int(match.group(2).replace(',', ''))
        
    return salary_dict

# Example Usage with your text:
# Output: {'min': 218400, 'max': 365200}

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

def extract_field(text, field_name):
    # This regex looks for 'Field Name:', grabs everything after it, 
    # but stops before the next common field header (like 'Subcategory:' or 'Schedule:')
    match = False
    if field_name in text:
        
        pattern = rf"{field_name}:\s*(.*?)\s*(?=Category:|Subcategory:|Schedule:|Shift:|Travel:|Minimum Clearance|$)"
        match = re.search(pattern, text, re.IGNORECASE)
        print(field_name,match)
    return match.group(1).strip() if match else "N/A"

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
        
        role_node = soup.find("h1")
        role_name = role_node.get_text(strip=True) if role_node else "Unknown Role"
        
        company_node = soup.find("a", {"data-wa-click": "djv-job-company-profile-click"})
        company_name = company_node.get_text(strip=True) if company_node else "Unknown Company"

        # 1. Extract Skills (The InfoBadges)
        skills = []
        skill_nodes = soup.select(".SeuiInfoBadge div")
        if skill_nodes:
            skills = [s.get_text(strip=True) for s in skill_nodes if s.get_text(strip=True)!='Create job alert']
        
        # skills_str = "Skills: " + ", ".join(skills) if skills else ""

        # 2. Extract Description Summary
        # Note: Dice uses a dynamic class that starts with 'job-detail-description-module'
        desc_node = soup.find("div", class_=lambda x: x and 'jobDescription' in x)
        
        # Fallback if the specific class above fails
        if not desc_node:
            desc_node = soup.find(id="jobDescription") or soup.select_one(".job-details-body")

        full_text = desc_node.get_text(separator="\n", strip=True) if desc_node else ""

        # 3. Combine them for a complete picture
        # print(f'Skills: {skills_str}')
        # print(f'full_text: {full_text}')
        details ={'link':url,
                  'role_name':role_name,
                  'company':company_name}
        return {"full_text":full_text,"skills":skills[3:],'job_details':details} if full_text.strip() else "Full text container not found."

    except Exception as e:
        return f"Error fetching details: {e}"
    


def expand_job_details(content):
    
    """
    Parses the massive text block from Dice to extract structured ATS data.
    """
    skills =content['skills']
    # cprint(skills,color = "blue")
    full_text = content['full_text']
    base_info =content['job_details']
    # Split the text at 'Category:', grab the second half, 
    # then normalize all whitespace into single spaces.
    if 'Category:' in full_text:
        raw_segment = full_text.split('Category:')[1]
        is_category_needed = True
    else:
        raw_segment = full_text
        is_category_needed = False

    # 2. Use Regex to replace ALL whitespace (tabs, newlines, multiple spaces) with one single space
    cleaned_description = re.sub(r'\s+', ' ', raw_segment).strip()

    # 3. Final string
    prefix = "Category: " if is_category_needed else ""
    description = f"{prefix}{cleaned_description}" f"Category: {cleaned_description}"

    # cprint(full_text)
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
    # salary_pattern = r'Target salary range:\s*\$(\d{1,3}(?:,\d{3})*)\s*-\s*\$(\d{1,3}(?:,\d{3})*)'
    # salary_match = re.search(salary_pattern, full_text)
    # cprint(full_text,color='green')
    # salary_dict = {"min": 0, "max": 0}
    # if salary_match:
    #     salary_dict["min"] = int(salary_match.group(1).replace(',', ''))
    #     salary_dict["max"] = int(salary_match.group(2).replace(',', ''))
    salary_dict =extract_salary(full_text)
    # 4. Build the final dictionary
    # Check the type and the content
    description = description.replace(" '",'')

    extracted_fields = {
        "category": extract_field(description, "Category"),
        "subcategory": extract_field(description, "Subcategory"),
        "schedule": extract_field(description, "Schedule"),
        "shift": extract_field(description, "Shift"),
        "travel": extract_field(description, "Travel"),
    }
    cprint(base_info.get("link"))
    if 'Description' in full_text:
        raw_description = full_text.split('Description')[1]
    elif 'Duties' in full_text:
        raw_description = full_text.split('Duties')[1]
    elif 'Summary' in full_text:
        raw_description = full_text.split('Summary')[1]
    elif 'RESPONSIBILITIES' in full_text:
        raw_description = full_text.split('RESPONSIBILITIES')[1]
    elif 'Responsibilities' in full_text:
        raw_description = full_text.split('Responsibilities')[1]
    else:
        cprint(full_text,color ='blue')
        raw_description = full_text
    results = {
        "role_name": base_info.get("role_name") if base_info else "Unknown",
        "company": base_info.get("company") if base_info else "Unknown",
        "link": base_info.get("link") if base_info else "N/A",
        "detials":extracted_fields,
        "requirements": {
            "years_exp": years_exp,
            "clearance": clearance,
            "polygraph": has_poly,
            "remote": "No" if "Potential for Remote Work: No" in full_text else "Yes/Hybrid",
            "skills":skills
        },

        "compensation": salary_dict,
        "raw_description": raw_description 
    }
    # pprint(results)
    return results

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

# print(locals())
# print(f"Found {len(job_links)} jobs.")
# print(job_links)

if __name__ =="__main__":
    # 1. Setup the directory
    output_dir = "JobData/Dice/llmIn"
    os.makedirs(output_dir, exist_ok=True)


    
    seen_links = set()

    # 2. Start the Pagination Loop
    totalPages = get_total_pages(search_url)

    cprint(f"🚀 Starting scrape. Total pages to scan: {totalPages}", color='cyan')

for page_num in range(1, totalPages + 1):
    page_url = f'{search_url}&page={page_num}'
    job_links = get_dice_links(page_url)
    all_extracted_jobs = []
    for jobURL in job_links:
        final_job = expand_job_details(get_full_job_details(jobURL))
        break
#     current_url = f"{search_url}&page={page_num}"
#     cprint(f"[+] Scraping Page {page_num}: {current_url}", color='green')
    
#     # 1. Get the HTML of the SEARCH RESULTS page
#     headers = {"User-Agent": "Mozilla/5.0 ..."} # Use your headers
#     response = requests.get(current_url, headers=headers)
#     soup = BeautifulSoup(response.text, 'html.parser')

#     # 2. Find the actual job card elements on the page
#     # Dice usually uses 'd-job-card' or a specific div for each result
#     job_cards = soup.select('d-job-card') 
    
#     if not job_cards:
#         cprint(f"  [!] No job cards found on page {page_num}.", color='yellow')
#         break

#     for idx, card in enumerate(job_cards, start=1):
#         # NOW 'card' is a Tag object, so select_one will work!
#         link_node = card.select_one('a[data-testid="job-search-job-card-link"]')
#         if not link_node: continue
        
#         role_link = link_node.get('href')
#         if not role_link or role_link in seen_links: continue

#         # 3. Now deep-scrape the individual job page
#         raw_description = get_full_job_details(role_link)

#         # 4. Build base data using card-level info
#         base_data = {
#             "role_name": link_node.get_text(strip=True),
#             "company": card.select_one('[data-testid="search-result-item-company-name"]').get_text(strip=True) if card.select_one('[data-testid="search-result-item-company-name"]') else "Unknown",
#             "link": role_link,
#             "location": card.select_one('[data-testid="search-result-item-location"]').get_text(strip=True) if card.select_one('[data-testid="search-result-item-location"]') else "N/A",
#             "full_description": raw_description
#         }

#         # 5. Run your expansion logic
#         final_job = expand_job_details_(base_data) # Note the underscore if that's your function name
    all_extracted_jobs.append(final_job)
#         seen_links.add(role_link)

            # Respectful scraping: Jitter between deep scrapes
        #     time.sleep(random.uniform(1.5, 3.0))

        # cprint(f"--- Finished Page {page_num} | Total Jobs: {len(all_extracted_jobs)} ---", color='yellow')

    # 5. Save to JSON
    filename = f"{output_dir}Dice_Scrape_{page_num}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_extracted_jobs, f, indent=4)

    cprint(f"🎉 SUCCESS! Saved {len(all_extracted_jobs)} jobs to {filename}", color='green')