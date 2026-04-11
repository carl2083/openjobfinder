# JobFinder

JobFinder is a desktop tool that helps you review Seek jobs, send job descriptions to ChatGPT, and save the results to Excel and optional PDF output.

## 1. Run It

### Windows

```bash
git clone https://github.com/carl2083/openjobfinder
cd openjobfinder
python -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
copy config.example.json config.json
python jobfinder_ui.py
```

Then:

- Fill `Basic Setup`: location, keyword, run count or a single JD URL.
- Fill `Advanced` only if you need to override paths or URLs.
- Click the main button once to launch Debug Chrome.
- Log in to Seek and ChatGPT in that browser.
- Click the same button again to continue the run.

### macOS

```bash
git clone https://github.com/carl2083/openjobfinder
cd openjobfinder
python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip setuptools wheel
pip install --no-compile -r requirements.txt
cp config.example.json config.json
python3 jobfinder_ui.py
```

Then:

- Fill `Basic Setup`: location, keyword, run count or a single JD URL.
- Fill `Advanced` only if you need to override paths or URLs.
- Click the main button once to launch Debug Chrome.
- Log in to Seek and ChatGPT in that browser.
- Click the same button again to continue the run.

## 2. Other Info

- Python 3.8+ is required.
- Upgrading `pip`, `setuptools`, and `wheel` is recommended before installing dependencies.
- If you pulled a newer version of the app, run `pip install -r requirements.txt` again so `PySide6` is installed.
- `Edit skill.md` creates a default template for new users, including a "Copy this to ChatGPT" prompt for building a reusable skills profile.
- `Edit prompt` opens the main JD / resume / cover-letter prompt template.
- In `Advanced`, you can choose both `Resume Style` and `Cover Letter Style`.
- Cover letters are guided to stay close to one page, usually 250-400 words, across 3-6 paragraphs, focused on key qualifications instead of repeating the full resume.
- Output goes to `job_results.xlsx` by default, plus `pdf_output/<job_id>/` when PDF export is enabled.
- If Chrome is installed in a non-standard location, set `chrome_path` manually.
- Generated resumes and cover letters should always be reviewed before use.
- This tool automates third-party websites, so Seek or ChatGPT UI changes can affect reliability on both Windows and macOS.
