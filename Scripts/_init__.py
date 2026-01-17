import sys,os
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from common.helper import cprint

ClearanceJobsdirectory = ""
subdirectories = [ "llmOut", "llmIn"]
    
directories = [
    "JobData/ClearanceJobs",
    "JobData/LinkedinJobs",
    "JobData/DiceJobs",
    "JobData/BuiltInJobs",]
for directory in directories:
    baseDirectory = directory
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
    for subdirectory in subdirectories:
        directory = os.path.join(baseDirectory, subdirectory)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)  
            cprint(f"Created directory: {directory}", color = "green")
if not os.path.exists("Resumes/"):
    os.makedirs("Resumes/", exist_ok=True)  
    cprint(f"Created directory: Resumes/", color = "green")