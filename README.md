# JobFinder

JobFinder is a desktop tool that helps you review Seek jobs, send job descriptions to ChatGPT, and save the results to Excel and optional PDF output.

## 1. Run It

### Windows

```bash
git clone https://github.com/carl2083/openjobfinder
cd OpenJobFinder
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy config.example.json config.json
python jobfinder_ui.py
```

Then:

- fill the essentials in the UI:
  - `Basic Setup`: location, keyword, run count or single JD URL
  - `Advanced`: Chrome path only if auto-detect does not work
- click the main action button once to launch Debug Chrome
- log in to Seek and ChatGPT in that Chrome window
- click the same button again to continue and start the run

### macOS

```bash
git clone https://github.com/carl2083/openjobfinder
cd OpenJobFinder
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
python3 jobfinder_ui.py
```

Then:

- fill the essentials in the UI:
  - `Basic Setup`: location, keyword, run count or single JD URL
  - `Advanced`: Chrome path if auto-detect does not work
- click the main action button once to launch Debug Chrome
- log in to Seek and ChatGPT in that Chrome window
- click the same button again to continue and start the run

## 2. Other Info

- Python 3.8+ is required.
- Upgrading `pip` first is recommended if dependency installation fails, but it is not required before setup.
- `编辑 skill.md` creates a default template for new users, including a “Copy this to ChatGPT” prompt for building a reusable skills profile.
- `编辑 prompt` opens the main JD / resume / cover-letter prompt template.
- In `Advanced`, you can choose both `Resume Style` and `Cover Letter Style`.
- Current cover letter prompt guidance is:
  - ideally one page
  - generally 250-400 words
  - 3-6 paragraphs
  - focused on key qualifications instead of repeating the full resume
- Output goes to:
  - Excel: `job_results.xlsx` by default
  - PDF: `pdf_output/<job_id>/` when PDF export is enabled
- If Chrome is installed in a non-standard location, set `chrome_path` manually.
- Generated resumes and cover letters should always be reviewed before use.
- This tool automates third-party websites, so Seek or ChatGPT UI changes can affect reliability on both Windows and macOS.
