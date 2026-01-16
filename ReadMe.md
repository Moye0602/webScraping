### The purpose
- As former Officer of the USMC I departed with hope then Covid happened
- For those who also had hope, which may have dwindled due to lost opportunities and automation removal of roles.
- Consider this an attempt to balance the scales.

### How to use
- You will need to get your own API key from Google Gemini and place it in a .env file
    - the format expected:
        - GENAI_API_KEY="Your key goes here"
- Run these files in this order
    - wsClearanceJobs.py
        - Scans ClearanceJobs.com in batches of 20 (only 20 are shown per page)
        - this will generate  a set of json files per page of the details per role found from the webscraper searching page for page
        - the process takes aproximate 2 minutes per 600 (more or less dependings or your computers ability to use threading)
    - atsCleareance.Jobs.py
        - In batches of 30 this will compare youre resume against roles found and store in json files from the previous scan. 
        - Using the Gemini model chosen, it will give a score, explanaition of the score and what information is missing form your resume to become a   better candidate for each role
        - The output will generate a batch of json files per json file read with each new file containing only the remainng jobs of scores above 80% match and the salaray expectation
    - sort_llm_results.py
        - This final file will generate a master analysis file which will have a combination of all jobs matching user criteria in one file and display the contents ranked descending from best match with the follwoing details
            - score
            - company
            - role name
            - geographic location
            - link (which is clickable)

### AI is not a replacement for humans on the ends
    - while this will aid in matching a person to roles list on the job site, it is only as good as the resume you give it
    - There will be minor improvements so long as I also use this and develop it until I land a job from this. I am always open to working with other to improve upon things that can help others

