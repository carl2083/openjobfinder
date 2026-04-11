You are evaluating job descriptions for me.
Please deeply analyse this job posting, the company and its industry.
based on your analysis, identify the most important 9 - 12 skills that are most relevant to the role,
and list those as 1-2 word long keywords sets that I can include in my resume.

EXPERIENCE CONSTRAINT (CRITICAL):
- ONLY include job roles, employers, and position titles that I explicitly provide.
- DO NOT invent, rename, generalise, or group experience into new roles (e.g. "Residential Projects", "Consulting Work", "Various Clients").
- If experience does not belong to a formal employer or job title, it must be labelled exactly as provided by me (e.g. "Business Owner - Cafe", "Self-Directed Projects").
- DO NOT create new time ranges or fill perceived employment gaps with inferred roles.

Then write me a resume IMPORTANT RULES (DO NOT IGNORE):
- DO NOT make up, exaggerate, or fabricate any experience, responsibilities, tools, systems, or results.
- ONLY use experience that can be reasonably inferred from my actual background.
- You may reframe, emphasize, or de-emphasize aspects of my real experience to best match the JD, but never introduce new experience.
- If a JD requirement is not directly met, use the closest transferable or adjacent experience instead and clearly reflect it truthfully.
- For EACH job experience, write 6-10 bullet points (never fewer than 6).
- Bullet points MUST be tailored to the job description and map directly to its responsibilities and requirements.
- You may reframe or emphasize different aspects of my experience to match the JD, but do NOT invent experience.
- Every bullet point MUST follow the X-Y-Z formula:
  - X = what was accomplished
  - Y = how it was accomplished (tools, methods, stakeholders)
  - Z = measurable outcome or business impact (%, $, time, scale). If exact metrics are unavailable, use reasonable qualitative impact.

ALIGNMENT REQUIREMENTS:
- Ensure ALL major responsibilities in the JD are reflected somewhere in the bullet points.
- If a JD requirement is missing from my background, show adjacent or transferable experience instead.
- Prioritize JD keywords, tools, systems, and methodologies in bullet points.

EXPERIENCE DEPTH:
- In the Professional Summary, explicitly state total years of relevant experience if applicable.
- Senior or long-term roles should have more bullet points than junior roles.

QUALITY BAR:
- No generic bullets.
- No duplicated ideas.
- No filler language.
- Bullets must sound like a strong Australian-market resume.

If fewer than 6 strong bullets exist for a role, derive additional bullets by:
- Breaking complex work into sub-achievements
- Highlighting stakeholder management, risk, compliance, reporting, or optimisation work

Resume must have the following format:
    - Professional Summary:
    - Skills:
    - Experience:
    - Education:
    - Certifications:
    - Languages:
    - References:
    (not strictly follow the format, just use it as a reference)
And write me a cover letter try answer the questions in JD.

COVER LETTER RULES:
- The cover letter should ideally fit on a single page.
- Keep it generally between 250 and 400 words.
- Structure it into 3 to 6 paragraphs.
- Focus on the strongest qualifications and fit for this role.
- Do not repeat the entire resume or restate every bullet point.
- Use specific, relevant evidence from my background that best supports this application.
- Keep it sharp, persuasive, and readable in an Australian job-market tone.

For bullet points use x,y,z formula: which is what you accomplished. and how you accomplished it. Then write me a resume and cover letter
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
        "resume_focus": ["", ""]
    },
    "other": {
        "resume_sections": {
            "name": "",
            "position": "",
            "address": "",
            "phone": "",
            "email": "",
            "professional_summary": "",
            "experience": [
                {
                    "company": "",
                    "location": "",
                    "role": "",
                    "date": "",
                    "bullets": ["", ""]
                }
            ],
            "education": [
                {
                    "institution": "",
                    "location": "",
                    "degree": ""
                }
            ],
            "skills": ["", ""]
        },
        "Cover Letter": ""
    }
}
Do not add commentary.
All scores must follow the defined scoring model.
