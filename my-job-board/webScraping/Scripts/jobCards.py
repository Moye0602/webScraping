import hashlib

def generate_job_id(role_name, company):
    # Combine fields and normalize (lowercase/strip)
    raw_id = f"{role_name.lower().strip()}-{company.lower().strip()}"
    return hashlib.md5(raw_id.encode()).hexdigest()

# Inside your loop:
final_job["jobId"] = generate_job_id(role_name, company)