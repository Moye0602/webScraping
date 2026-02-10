import pandas as pd
import json
import os

import hashlib

def generate_unique_id(role, company, link):
    """Creates a deterministic hash to use as a unique ID."""
    hash_input = f"{role}{company}{link}".encode('utf-8')
    return hashlib.md5(hash_input).hexdigest()



def save_for_react(winners_dict, file_path):
    flat_list = []
    for company, roles in winners_dict.items():
        for role_name, details in roles.items():
            # Merge the keys into the object
            job_entry = details.copy()
            job_entry['company'] = company
            job_entry['role_name'] = role_name # Now React can see job.role_name
            flat_list.append(job_entry)
            
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(flat_list, f, indent=4)
        

        
def filter_and_archive_master(min_threshold=85):
    # Compute paths relative to this script's location (portable across machines)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    master_path_IN = os.path.normpath(os.path.join(script_dir, '..', 'JobData', 'ClearanceJobs', 'llmIn', 'ATS_MASTER_ANALYSIS.json'))
    master_path_OUT = os.path.normpath(os.path.join(script_dir, '..', '..', 'src', 'MASTER_ANALYSIS.json'))
    archive_path = os.path.normpath(os.path.join(script_dir, '..', 'JobData', 'ClearanceJobs', 'llmIn', 'ARCHIVED_ANALYSIS.json'))
    
    if not os.path.exists(master_path_IN):
        print(f"❌ Source file not found: {master_path_IN}")
        return pd.DataFrame()

    # 1. Load the original source
    with open(master_path_IN, 'r', encoding='utf-8') as f:
        source_data = json.load(f)

    # Containers for our split
    winners_dict = {}
    archived_dict = {}
    flattened_winners = []

    # 2. Iterate and Delete (Split) logic
    for company, roles in source_data.items():
        for role_name, details in roles.items():
            score = int(details.get('score', 0))
            
            # Prepare the data object
            job_entry = details.copy()
            job_entry['company'] = company
            job_entry['role_name'] = role_name
            

            if score >= min_threshold:
                # Add to Winners
                if company not in winners_dict:
                    winners_dict[company] = {}
                details['id'] = generate_unique_id(role_name, company, job_entry.get('link', ''))
                winners_dict[company][role_name] = details
                flattened_winners.append(job_entry)
            else:
                # Add to Archived
                if company not in archived_dict:
                    archived_dict[company] = {}
                archived_dict[company][role_name] = details

    # 3. Save the Winners back to the main source file (Overwriting with clean data)
    with open(master_path_OUT, 'w', encoding='utf-8') as f:
        json.dump(winners_dict, f, indent=4)
    
    # 4. Save the Filtered-out roles to the Archive file
    with open(archive_path, 'w', encoding='utf-8') as f:
        json.dump(archived_dict, f, indent=4)

    save_for_react(winners_dict, master_path_OUT)
    # 5. Return a DataFrame for the "Winners" only
    df = pd.DataFrame(flattened_winners)
    if not df.empty:
        print(f"✅ Cleanup Complete!")
        print(f"🔥 Kept {len(flattened_winners)} roles in Master Analysis.")
        print(f"📁 Moved remaining roles to Archive.")
        
        display_cols = ['score', 'company', 'role_name', 'location', 'link']
        return df[display_cols].sort_values(by='score', ascending=False)
    
    return pd.DataFrame()

# Run the process
report = filter_and_archive_master(min_threshold=85)
if not report.empty:
    print(report.to_string(index=False))