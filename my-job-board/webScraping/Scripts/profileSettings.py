import os

# Thresholds / settings
minSalary = 110000
minScore = 90
atsBatchSize = 30
llmModel = 'models/gemini-2.5-flash-lite'

# Relative locations (kept for backward compatibility across scripts)
ws_root_directory = "JobData/ClearanceJobs"
# MASTER_ANALYSIS_PATH = 'JobData/ClearanceJobs/MASTER_ANALYSIS.json'
APPLIED_TRACKER_PATH = 'JobData/ClearanceJobs/applied_jobs.json'
webscraped_jobs_path = 'JobData/ClearanceJobs/jobs_data.json'
ws_data_path_In = 'JobData/ClearanceJobs/llmIn/'
ws_data_path_Out = 'JobData/ClearanceJobs/llmOut/'

# Absolute paths computed relative to this `Scripts` folder so all scripts can import
# and use consistent absolute locations when needed.
RESUME_PATH_UPLOADS = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'Resumes_Uploads'))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WS_ROOT_ABS = os.path.normpath(os.path.join(SCRIPT_DIR, '..', ws_root_directory))
MASTER_ANALYSIS_PATH_ABS = os.path.join(WS_ROOT_ABS, 'MASTER_ANALYSIS.json')
APPLIED_TRACKER_PATH_ABS = os.path.join(WS_ROOT_ABS, 'applied_jobs.json')
webscraped_jobs_path_ABS = os.path.join(WS_ROOT_ABS, 'jobs_data.json')
ws_data_path_In_ABS = os.path.join(WS_ROOT_ABS, 'llmIn')
ws_data_path_Out_ABS = os.path.join(WS_ROOT_ABS, 'llmOut')


# Example helper for scripts that want to prefer absolute paths but fall back to relative
# def resolve_path(rel: str, abs_candidate: str) -> str:
# 	"""Return an absolute path if it exists, otherwise return the relative path."""
# 	try:
# 		if os.path.exists(abs_candidate):
# 			return abs_candidate
# 	except Exception:
# 		pass
# 	return rel

# import os

def resolve_path(rel: str, abs_candidate: str) -> str:
    """
    Return abs_candidate if it exists. 
    If not, create the directory structure for abs_candidate and return it.
    Falls back to rel if an error occurs.
    """
    try:
        if os.path.exists(abs_candidate):
            return abs_candidate
        
        # Extract the directory portion of the absolute path
        abs_dir = os.path.dirname(abs_candidate)
        
        if abs_dir:
            # Create the directories (including parents) if they don't exist
            os.makedirs(abs_dir, exist_ok=True)
            
        # Return the absolute path now that its home exists
        return abs_candidate
    
    except Exception as e:
        # Fallback to relative path if permission denied or path is invalid
        print(f"⚠️ Warning: Could not create/resolve {abs_candidate}: {e}")
        return rel
# minSalary = 110000
# minScore = 90
# atsBatchSize = 30
# llmModel = 'models/gemini-2.5-flash-lite'
# ws_root_directory = "JobData/ClearanceJobs"
# webscraped_jobs_path = 'JobData/ClearanceJobs/jobs_data.json'
# ws_data_path_In = 'JobData/ClearanceJobs/llmIn/'
# ws_data_path_Out = 'JobData/ClearanceJobs/llmOut/'
# MASTER_ANALYSIS_PATH = 'JobData/ClearanceJobs/MASTER_ANALYSIS.json'
# APPLIED_TRACKER_PATH = 'JobData/ClearanceJobs/applied_jobs.json'

