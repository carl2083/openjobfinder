import json
import os
import random
import re
from pathlib import Path
from zipfile import BadZipFile
from dataclasses import dataclass
from dataclasses import fields
from datetime import datetime
from typing import Any, Dict, List, Optional

from openpyxl import Workbook, load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.worksheet.dimensions import RowDimension


DEFAULT_CONFIG_PATH = "config.json"
SKILL_PROFILE_PATH = "skill.md"


PROMPT_TEMPLATE = """
You are evaluating job descriptions for me.
Please deeply analyse this job posting, the company and its industry. 
based on your analysis, identify the most important 9 - 12 skills that are most relevant to the role, 
and list those as 1-2 word long keywords sets that I can include in my resume. 

EXPERIENCE CONSTRAINT (CRITICAL):
- ONLY include job roles, employers, and position titles that I explicitly provide.
- DO NOT invent, rename, generalise, or group experience into new roles (e.g. “Residential Projects”, “Consulting Work”, “Various Clients”).
- If experience does not belong to a formal employer or job title, it must be labelled exactly as provided by me (e.g. “Business Owner – Café”, “Self-Directed Projects”).
- DO NOT create new time ranges or fill perceived employment gaps with inferred roles.


Then write me a resume IMPORTANT RULES (DO NOT IGNORE):
- DO NOT make up, exaggerate, or fabricate any experience, responsibilities, tools, systems, or results.
- ONLY use experience that can be reasonably inferred from my actual background.
- You may reframe, emphasize, or de-emphasize aspects of my real experience to best match the job description, but never introduce new experience.
- If a JD requirement is not directly met, use the closest transferable or adjacent experience instead and clearly reflect it truthfully.
- For EACH job experience, write 6–10 bullet points (never fewer than 6).
- Bullet points MUST be tailored to the job description and map directly to its responsibilities and requirements.
- You may reframe or emphasize different aspects of my experience to match the JD, but do NOT invent experience.
- Every bullet point MUST follow the X–Y–Z formula:
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
"""


SHEET_HEADERS = [
    "Job ID",
    "Job Title",
    "Company",
    "Location",
    "Job URL",
    "Core Skill Match (0–30)",
    "Tools / Systems (0–20)",
    "Industry Gatekeeping (0–15)",
    "Seniority Fit (0–15)",
    "ATS Keyword Match (0–10)",
    "Location / Logistics (0–10)",
    "Suitability Total",
    "Nature of Work (0–30)",
    "Structure vs Chaos (0–20)",
    "Learning Value (0–20)",
    "Energy Drain (0–20) 0 is most draining, 20 is least draining",
    "Exit Value (0–10)",
    "Interest Total",
    "Final Score",
    "Recommendation (APPLY/MAYBE/SKIP)",
    "Confidence",
    "Top Strengths",
    "Main Risks",
    "Resume Focus",
    "Applied? (Y/N)",
    "Interview Outcome",
    "Notes",
    "Resume",
    "Cover Letter",
    "PDF Folder Link",
]


@dataclass
class Config:
    output_excel: str = "job_results.xlsx"
    job_location: str = "All Gold Coast QLD"
    keyword: Optional[str] = None
    gpt_mode: str = "web_chatgpt"
    max_runs: Optional[int] = 20
    single_job_url: Optional[str] = None
    include_recommendations: bool = False
    include_new_to_you: bool = False
    exit_when_done: bool = False
    skip_title_contains: str = ""
    delay_between_jobs_min_sec: int = 30
    delay_between_jobs_max_sec: int = 90
    batch_size: int = 1
    apply_threshold: int = 140
    maybe_threshold: int = 100
    default_confidence: str = "MEDIUM"
    chrome_debug_port: int = 9222
    chrome_user_data_dir: str = ""
    chrome_path: str = ""
    seek_url: str = "https://www.seek.com.au/"
    chatgpt_url: str = "https://chat.openai.com/"
    chatgpt_chat_title: str = "Job application advice"
    enable_local_sync: bool = False
    local_sync_path: str = ""
    local_sync_pull_before_run: bool = True
    enable_pdf_export: bool = False
    pdf_css_path: str = ""
    pdf_output_dir: str = "pdf_output"
    pdf_template_path: str = "templates/navy-gold-template.html"
    user_address: str = ""
    user_phone: str = ""
    user_email: str = ""
    user_name: str = "carl chen"


def load_config(path: str) -> Config:
    if not os.path.exists(path):
        return Config()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    allowed = {field.name for field in fields(Config)}
    sanitized = {key: value for key, value in data.items() if key in allowed}
    return Config(**sanitized)


def save_config(path: str, config: Config) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config.__dict__, f, indent=2)


def load_job_ids_from_excel(path: str) -> List[str]:
    if not os.path.exists(path):
        return []
    try:
        wb = load_workbook(path, read_only=True)
    except (BadZipFile, InvalidFileException):
        # 文件存在但不是合法的 xlsx，避免直接崩溃
        return []
    ws = wb.active
    ids: List[str] = []
    for row in ws.iter_rows(min_row=2, max_col=1, values_only=True):
        value = row[0]
        if value:
            ids.append(str(value).strip())
    return ids


def extract_job_id(job_url: str) -> Optional[str]:
    if not job_url:
        return None
    match = re.search(r"/job/(\d+)", job_url)
    if match:
        return match.group(1)
    # Seek 等站点可能用 /job/12345678，兜底：取 URL 中 6 位以上数字
    fallback = re.search(r"(\d{6,})", job_url)
    return fallback.group(1) if fallback else None


def compute_totals(payload: Dict[str, Any]) -> Dict[str, int]:
    suitability = payload.get("suitability") or {}
    interest = payload.get("interest") or {}
    suitability_total = (
        suitability.get("core_skill_match", 0)
        + suitability.get("tools_systems_overlap", 0)
        + suitability.get("industry_gatekeeping", 0)
        + suitability.get("seniority_fit", 0)
        + suitability.get("ats_keyword_match", 0)
        + suitability.get("location_logistics", 0)
    )
    interest_total = (
        interest.get("nature_of_work", 0)
        + interest.get("structure_vs_chaos", 0)
        + interest.get("learning_value", 0)
        + interest.get("energy_drain", 0)
        + interest.get("exit_value", 0)
    )
    final_score = suitability_total + interest_total
    return {
        "suitability_total": suitability_total,
        "interest_total": interest_total,
        "final_score": final_score,
    }


def recommendation_for(score: int, config: Config) -> str:
    if score >= config.apply_threshold:
        return "APPLY"
    if score >= config.maybe_threshold:
        return "MAYBE"
    return "SKIP"


def format_list(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if v)
    return str(value) if value is not None else ""


def load_skill_profile(path: str = SKILL_PROFILE_PATH) -> str:
    if not os.path.exists(path):
        return ""
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except Exception:
        return ""


def build_prompt(job_description: str) -> str:
    skill_profile = load_skill_profile()
    skill_block = ""
    if skill_profile:
        skill_block = (
            "SKILL PROFILE (source of truth; do not fabricate beyond this):\n"
            f"{skill_profile}\n\n"
        )
    return f"{PROMPT_TEMPLATE}\n\n{skill_block}JOB DESCRIPTION:\n{job_description}"


def extract_json_from_text(text: str) -> Dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return json.loads(fenced.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in ChatGPT response.")
    return json.loads(text[start : end + 1])


def build_row(payload: Dict[str, Any], config: Config) -> List[Any]:
    job_meta = payload.get("job_meta") or {}
    suitability = payload.get("suitability") or {}
    interest = payload.get("interest") or {}
    notes = payload.get("notes", {})
    other = payload.get("other", {})

    job_id = extract_job_id(job_meta.get("job_url", "")) or job_meta.get("job_id")
    if not job_id:
        job_url = job_meta.get("job_url", "")
        job_id = (job_url.rstrip("/").split("/")[-1] or "unknown") if job_url else "unknown"

    totals = compute_totals(payload)
    recommendation = recommendation_for(totals["final_score"], config)

    pdf_folder_path = os.path.abspath(os.path.join(config.pdf_output_dir, str(job_id)))
    pdf_folder_link = f"file:///{pdf_folder_path.replace(os.sep, '/')}"

    return [
        job_id,
        job_meta.get("job_title", ""),
        job_meta.get("company", ""),
        job_meta.get("location", ""),
        job_meta.get("job_url", ""),
        suitability.get("core_skill_match", 0),
        suitability.get("tools_systems_overlap", 0),
        suitability.get("industry_gatekeeping", 0),
        suitability.get("seniority_fit", 0),
        suitability.get("ats_keyword_match", 0),
        suitability.get("location_logistics", 0),
        totals["suitability_total"],
        interest.get("nature_of_work", 0),
        interest.get("structure_vs_chaos", 0),
        interest.get("learning_value", 0),
        interest.get("energy_drain", 0),
        interest.get("exit_value", 0),
        totals["interest_total"],
        totals["final_score"],
        recommendation,
        config.default_confidence,
        format_list(notes.get("top_strengths")),
        format_list(notes.get("main_risks")),
        format_list(notes.get("resume_focus")),
        "",
        "",
        format_list(notes.get("notes")),
        format_list(other.get("Resume", notes.get("Resume"))),
        format_list(other.get("Cover Letter", notes.get("Cover Letter"))),
        pdf_folder_link,
    ]


def ensure_workbook(path: str) -> Workbook:
    if os.path.exists(path):
        try:
            return load_workbook(path)
        except (BadZipFile, InvalidFileException):
            # 备份损坏文件，避免覆盖并保留现场
            ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
            backup_path = f"{path}.corrupt-{ts}.xlsx"
            os.replace(path, backup_path)
    wb = Workbook()
    ws = wb.active
    ws.title = "Jobs"
    ws.append(SHEET_HEADERS)
    wb.save(path)
    return wb


def _parse_skip_title_strings(s: str) -> List[str]:
    if not s or not s.strip():
        return []
    # 支持英文逗号 , 和中文逗号 ，
    parts = re.split(r"[,，]", s)
    return [p.strip().lower() for p in parts if p.strip()]


def _job_title_matches_skip(job_title: str, skip_strings: List[str]) -> Optional[str]:
    if not skip_strings:
        return None
    title_lower = (job_title or "").lower()
    title_words = re.findall(r"[a-z0-9]+", title_lower)
    for k in skip_strings:
        if not k:
            continue
        if k in title_lower:
            return k
        for w in title_words:
            if k in w or w in k:
                return k
    return None


def should_skip_job_by_title(job_title: str, config: Config) -> Optional[str]:
    skip_strings = _parse_skip_title_strings(getattr(config, "skip_title_contains", "") or "")
    return _job_title_matches_skip(job_title, skip_strings)


def append_skipped_job_to_excel(
    config: Config, job_meta: Dict[str, Any], skip_reason: str
) -> str:
    job_id = extract_job_id(job_meta.get("job_url", "")) or job_meta.get("job_id")
    if not job_id:
        job_url = job_meta.get("job_url", "")
        job_id = (job_url.rstrip("/").split("/")[-1] or "unknown") if job_url else "unknown"
    payload = {
        "job_meta": {**job_meta, "job_id": job_id},
        "suitability": {},
        "interest": {},
        "notes": {"notes": [f"跳过: {skip_reason}"]},
        "other": {},
    }
    for k in ["core_skill_match", "tools_systems_overlap", "industry_gatekeeping",
              "seniority_fit", "ats_keyword_match", "location_logistics"]:
        payload["suitability"][k] = 0
    for k in ["nature_of_work", "structure_vs_chaos", "learning_value",
              "energy_drain", "exit_value"]:
        payload["interest"][k] = 0
    # build_row needs suitability/interest totals - use 0
    payload["suitability_total"] = 0
    payload["interest_total"] = 0
    payload["final_score"] = 0
    # build_row expects standard structure; pass minimal
    fake_payload = {
        "job_meta": payload["job_meta"],
        "suitability": payload["suitability"],
        "interest": payload["interest"],
        "notes": payload["notes"],
        "other": payload["other"],
    }
    skip_note = f"跳过: 标题包含 {skip_reason}"
    row = [
        job_id,
        job_meta.get("job_title", ""),
        job_meta.get("company", ""),
        job_meta.get("location", ""),
        job_meta.get("job_url", ""),
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        "SKIP",
        config.default_confidence,
        "", "", "", "", "", skip_note, "", "", "",
    ]
    wb = ensure_workbook(config.output_excel)
    ws = wb.active
    ws.append(row)
    row_num = ws.max_row
    dim = RowDimension(ws, index=row_num, hidden=True)
    ws.row_dimensions[row_num] = dim
    url_cell = ws.cell(row=row_num, column=5)
    if url_cell.value:
        url_cell.hyperlink = url_cell.value
        url_cell.style = "Hyperlink"
    wb.save(config.output_excel)
    return job_id


def append_row_to_excel(config: Config, payload: Dict[str, Any]) -> str:
    wb = ensure_workbook(config.output_excel)
    ws = wb.active
    row = build_row(payload, config)
    ws.append(row)
    # 将 Job URL 设置为可点击的超链接
    url_cell = ws.cell(row=ws.max_row, column=5)
    if url_cell.value:
        url_cell.hyperlink = url_cell.value
        url_cell.style = "Hyperlink"
    # PDF 文件夹链接 (AD 列)
    pdf_link_cell = ws.cell(row=ws.max_row, column=30)
    if pdf_link_cell.value:
        pdf_link_cell.hyperlink = pdf_link_cell.value
        pdf_link_cell.style = "Hyperlink"
    wb.save(config.output_excel)
    return str(row[0])
