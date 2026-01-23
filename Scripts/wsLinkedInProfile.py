import json, os
from pprint import pprint
from bs4 import BeautifulSoup
from icecream import ic
import requests
import time,random
import concurrent.futures
from datetime import datetime
import  _init__
from common.helper import cprint 

def fetch_linkedin_profile(linkedin_url, headers):
    """Fetches and parses a LinkedIn profile page."""
    # try:
    response = requests.get(linkedin_url, headers=headers)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    
    profile_data = {}
    
    
    
    profile_data['name'] = soup.find('h1', {'class': 'text-heading-xlarge'})
    print(profile_data['name'])
    # .get_text(strip=True)
    # profile_data['headline'] = soup.find('div', {'class': 'text-body-medium'}).get_text(strip=True)
    # profile_data['location'] = soup.find('span', {'class': 'text-body-small'}).get_text(strip=True)
    
    experience_section = soup.find('section', {'id': 'experience-section'})
    experiences = []
    if experience_section:
        for exp in experience_section.find_all('li', {'class': 'pv-entity__position-group-pager'}):
            title = exp.find('h3').get_text(strip=True) if exp.find('h3') else ''
            company = exp.find('p', {'class': 'pv-entity__secondary-title'}).get_text(strip=True) if exp.find('p', {'class': 'pv-entity__secondary-title'}) else ''
            duration = exp.find('h4', {'class': 'pv-entity__date-range'}).get_text(strip=True) if exp.find('h4', {'class': 'pv-entity__date-range'}) else ''
            experiences.append({'title': title, 'company': company, 'duration': duration})
    
    profile_data['experiences'] = experiences
    return profile_data
    # except Exception as e:
    #     cprint(f"Error fetching LinkedIn profile: {e}", "red")
    #     return None

# --- EXECUTION EXAMPLE ---
linkedin_url = "https://www.linkedin.com/in/some-profile/"
# userPorfile = input("Enter your LinkedIn profile URL (for headers): ")
userPorfile = "https://www.linkedin.com/in/kristopher-moye/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Cookie': f'li_at={userPorfile};'
}
profile_data = fetch_linkedin_profile(linkedin_url, headers)
if profile_data:
    pprint(profile_data)