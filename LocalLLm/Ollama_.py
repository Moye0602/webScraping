import subprocess
import ollama
import json
import time

def ensure_ollama_is_ready():
    """Checks if Docker container is running and model is pulled."""
    try:
        # Check if the container 'ollama' is running
        status = subprocess.check_output(['docker', 'inspect', '-f', '{{.State.Running}}', 'ollama'])
        if b'true' not in status:
            print("Starting Ollama container...")
            subprocess.run(['docker', 'start', 'ollama'])
            time.sleep(5) # Wait for service to boot
    except subprocess.CalledProcessError:
        print("Ollama container not found. Please run your 'docker run' command first.")

def send_batch_to_local_llm(resume_text, jobs_batch):
    """Sends a list of jobs to the local Docker model."""
    
    # Format the batch into a single string
    jobs_formatted = ""
    for idx, job in enumerate(jobs_batch):
        jobs_formatted += f"--- JOB ID: {idx} ---\n{job['full_description'][:1500]}\n"

    prompt = f"""
    SYSTEM: You are an ATS matching expert. 
    Compare this RESUME to the following {len(jobs_batch)} JOBS.
    
    RESUME:
    {resume_text}
    
    JOBS TO ANALYZE:
    {jobs_formatted}
    
    OUTPUT INSTRUCTIONS:
    Return ONLY a JSON array of objects. 
    Each object: {{"id": int, "score": int, "reason": "string"}}
    """

    # Sending the prompt via the Python library (which talks to Docker port 11434)
    response = ollama.chat(model='llama3.1:8b', messages=[
        {'role': 'user', 'content': prompt},
    ])
    
    return response['message']['content']

# --- EXECUTION ---
ensure_ollama_is_ready()
# result = send_batch_to_local_llm(my_resume, my_job_list[0:10])
# print(result)