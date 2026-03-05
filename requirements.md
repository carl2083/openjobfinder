# Python

# Setting UI 
    1. to set where to save the excel data: default google sheet url
    2. to set job location: default :"All Gold Coast QLD"
    3. to set key word: default: None
    4. load job ids(already looked at)
    5. option to choose from api chat gpt or webpage chatgpt(now only webpage chatgpt copy and paste the prompt to the webchatpgt and wait for response, api chatgpt greyed out). 
    6. option to run 5 times or 10 times or 20 times or 50, 100 times or indifinitly

# Use selemium to open seek.com and put all the settings and click on "seek", then go through every job under result. 
    1. skip job that in the loaded job ids. 
    2. open the Job and find: Job Title, Company, Location, Job URL, Job ID. 
    3. send prompt to the chosen option method (default website chatgpt) 
        You are evaluating job descriptions for me.
        Please deeply analyse this job posting, the company and its industry. based on your analysis, identify the top 10 technical skills, and 20 professional skills required for this role. list those as 1-2 word long keywords sets that I can include in my resume. make sure you mention how many years of exp directly in the professional summary. for bullet points use x,y,z formula: which is what you accomplished. and how you accomplished it. Then write me a resume and cover letter
        Return STRICT JSON using the provided schema.
        {
            "job_meta": {
                "job_title": "",
                "company": "",
                "location": "",
                "job_url": ""
            },
            "suitability": {
                "core_skill_match": 0,
                "tools_systems_overlap": 0,
                "industry_gatekeeping": 0,
                "seniority_fit": 0,
                "ats_keyword_match": 0,
                "location_logistics": 0
            },
            "interest": {
                "nature_of_work": 0,
                "structure_vs_chaos": 0,
                "learning_value": 0,
                "energy_drain": 0,
                "exit_value": 0
            },
            "notes": {
                "top_strengths": ["", ""],
                "main_risks": ["", ""],
                "resume_focus": ["", ""],
                "Resume": ["", ""],
                "Cover Letter": ["", ""]
            }
        }
        Do not add commentary.
        All scores must follow the defined scoring model.
    4. save the result to the excel:
        | Column | Description                       |
        | ------ | --------------------------------- |
        | A  | Job ID                           |
        | B  | Job Title                        |
        | C  | Company                          |
        | D  | Location                         |
        | E  | Job URL                          |
        | F  | Core Skill Match (0–30)          |
        | G  | Tools / Systems (0–20)           |
        | H  | Industry Gatekeeping (0–15)      |
        | I  | Seniority Fit (0–15)             |
        | J  | ATS Keyword Match (0–10)         |
        | K  | Location / Logistics (0–10)      |
        | L  | Suitability Total                |
        | M  | Nature of Work (0–30)            |
        | N  | Structure vs Chaos (0–20)        |
        | O  | Learning Value (0–20)            |
        | P  | Energy Drain (0–20)              |
        | Q  | Exit Value (0–10)                |
        | R  | Interest Total                   |
        | S  | Final Score                      |
        | T  | Recommendation (APPLY/MAYBE/SKIP)|
        | U  | Confidence                       |
        | V  | Top Strengths                    |
        | W  | Main Risks                       |
        | X  | Resume Focus                     |
        | Y  | Applied? (Y/N)                   |
        | Z  | Interview Outcome                |
        | AA | Notes                            |
        | AB | Resume                           |
        | AC | Cover Letter                     |

