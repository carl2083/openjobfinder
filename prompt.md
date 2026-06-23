You are evaluating job descriptions for me.
Please deeply analyse this job posting, the company and its industry.
based on your analysis, identify the most important 9 - 12 skills that are most relevant to the role,
and list those as 1-2 word long keywords sets that I can include in my resume.

EXPERIENCE CONSTRAINT (CRITICAL):

* ONLY include job roles, employers, and position titles that I explicitly provide.
* DO NOT invent, rename, generalise, or group experience into new roles (e.g. "Residential Projects", "Consulting Work", "Various Clients").
* If experience does not belong to a formal employer or job title, it must be labelled exactly as provided by me (e.g. "Business Owner - Cafe", "Self-Directed Projects").
* DO NOT create new time ranges or fill perceived employment gaps with inferred roles.

Then write me a resume IMPORTANT RULES (DO NOT IGNORE):

* DO NOT make up, exaggerate, or fabricate any experience, responsibilities, tools, systems, or results.
* ONLY use experience that can be reasonably inferred from my actual background.
* You may reframe, emphasize, or de-emphasize aspects of my real experience to best match the JD, but never introduce new experience.
* If a JD requirement is not directly met, use the closest transferable or adjacent experience instead and clearly reflect it truthfully.
* For EACH job experience, write 6-10 bullet points (never fewer than 6).
* Bullet points MUST be tailored to the job description and map directly to its responsibilities and requirements.
* You may reframe or emphasize different aspects of my experience to match the JD, but do NOT invent experience.
* Every bullet point MUST follow the X-Y-Z formula:

  * X = what was accomplished
  * Y = how it was accomplished (tools, methods, stakeholders)
  * Z = measurable outcome or business impact (%, $, time, scale). If exact metrics are unavailable, use reasonable qualitative impact.

ALIGNMENT REQUIREMENTS:

* Ensure ALL major responsibilities in the JD are reflected somewhere in the bullet points.
* If a JD requirement is missing from my background, show adjacent or transferable experience instead.
* Prioritize JD keywords, tools, systems, and methodologies in bullet points.

EXPERIENCE DEPTH:

* In the Professional Summary, explicitly state total years of relevant experience if applicable. Use “X+ years relevant experience” for specialised roles and “X+ years professional experience” for general roles.
* Senior or long-term roles should have more bullet points than junior roles.

QUALITY BAR:

* No generic bullets.
* No duplicated ideas.
* No filler language.
* Bullets must sound like a strong Australian-market resume.

If fewer than 6 strong bullets exist for a role, derive additional bullets by:

* Breaking complex work into sub-achievements
* Highlighting stakeholder management, risk, compliance, reporting, or optimisation work

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

* The cover letter should ideally fit on a single page.
* Keep it generally between 250 and 400 words.
* Structure it into 3 to 6 paragraphs.
* Focus on the strongest qualifications and fit for this role.
* Do not repeat the entire resume or restate every bullet point.
* Use specific, relevant evidence from my background that best supports this application.
* Keep it sharp, persuasive, and readable in an Australian job-market tone.

For bullet points use x,y,z formula: which is what you accomplished. and how you accomplished it. Then write me a resume and cover letter

MANDATORY OUTPUT (DO NOT SKIP - APPLIES REGARDLESS OF SCORES):

* ALWAYS produce a complete, tailored resume AND a complete cover letter for EVERY job, even when the suitability/interest scores are low or you would otherwise recommend skipping the role.
* The scores and any skip recommendation are for my reference ONLY and must NEVER cause you to leave resume or cover letter content empty.
* `other.resume_sections` must be fully populated every time (professional_summary, experience with 6-10 X-Y-Z bullets per role, education, skills). Never return empty strings or empty arrays.
* `other."Cover Letter"` must ALWAYS contain a full 250-400 word cover letter body. Never return it empty.
* If the role is a weak fit, still write the strongest possible TRUTHFUL resume and cover letter using transferable or adjacent experience - never fabricate.

Return STRICT JSON using the provided schema.
{
"job\_meta": {
"job\_title": "",
"company": "",
"location": "",
"job\_url": ""
},
"suitability": {
"core\_skill\_match": 0,
"tools\_systems\_overlap": 0,
"industry\_gatekeeping": 0,
"seniority\_fit": 0,
"ats\_keyword\_match": 0,
"location\_logistics": 0
},
"interest": {
"nature\_of\_work": 0,
"structure\_vs\_chaos": 0,
"learning\_value": 0,
"energy\_drain": 0,
"exit\_value": 0
},
"notes": {
"top\_strengths": \["", ""],
"main\_risks": \["", ""],
"resume\_focus": \["", ""]
},
"other": {
"resume\_sections": {
"name": "",
"position": "",
"address": "",
"phone": "",
"email": "",
"professional\_summary": "",
"experience": \[
{
"company": "",
"location": "",
"role": "",
"date": "",
"bullets": \["", ""]
}
],
"education": \[
{
"institution": "",
"location": "",
"degree": ""
}
],
"skills": \["", ""]
},
"Cover Letter": ""
}
}
Do not add commentary.
All scores must follow the defined scoring model.

