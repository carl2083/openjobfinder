import base64
import os
import random
import shutil
from pathlib import Path
from html import escape
import time
import re
from typing import Any, Callable, Dict, List, Optional, Tuple

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from jobfinder_core import (
    Config,
    COVER_LETTER_DESIGN_TEMPLATES,
    DEFAULT_COVER_LETTER_DESIGN,
    append_row_to_excel,
    append_skipped_job_to_excel,
    build_prompt,
    extract_job_id,
    extract_json_from_text,
    load_job_ids_from_excel,
    should_skip_job_by_title,
)


CHATGPT_HOSTS = ("chat.openai.com", "chatgpt.com")
SEEK_HOSTS = ("seek.com.au", "www.seek.com.au", "au.seek.com")

COVER_LETTER_TEMPLATE_PATH = "templates/cover-letter-template.html"

_CONTACT_ICON_SVGS = {
    "address": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5'
        'a2.5 2.5 0 110-5 2.5 2.5 0 010 5z"/></svg>'
    ),
    "email": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 4l-8 5-8-5'
        'V6l8 5 8-5v2z"/></svg>'
    ),
    "phone": (
        '<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M6.62 10.79a15.53 15.53 0 006.59 6.59l2.2-2.2a1 1 0 011.02-.24 11.36 11.36 0 003.56.57'
        ' 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1 11.36 11.36 0 00.57 3.56'
        ' 1 1 0 01-.24 1.02l-2.21 2.21z"/></svg>'
    ),
}


def _log(log: Optional[Callable[[str], None]], message: str) -> None:
    if log:
        log(message)


def connect_driver(config: Config) -> webdriver.Chrome:
    options = ChromeOptions()
    options.add_experimental_option(
        "debuggerAddress", f"127.0.0.1:{config.chrome_debug_port}"
    )
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.set_page_load_timeout(180)
        driver.set_script_timeout(180)
        driver.command_executor._timeout = 180  # 增加 Selenium 连接超时
    except Exception:
        pass
    return driver


def ensure_tab(
    driver: webdriver.Chrome, url_prefixes: Tuple[str, ...], target_url: str
):
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        current = driver.current_url
        if any(host in current for host in url_prefixes):
            return handle
    return _open_target_tab(driver, target_url)


def _current_url_for_handle(driver: webdriver.Chrome, handle: str) -> str:
    try:
        driver.switch_to.window(handle)
        return (driver.current_url or "").lower()
    except Exception:
        return ""


def _is_blank_tab_url(url: str) -> bool:
    current = (url or "").strip().lower()
    return current in {"", "about:blank", "chrome://newtab/", "chrome://new-tab-page/"}


def _open_blank_tab(driver: webdriver.Chrome) -> str:
    try:
        driver.switch_to.new_window("tab")
    except Exception:
        driver.execute_script("window.open('about:blank', '_blank');")
        time.sleep(0.3)
        driver.switch_to.window(driver.window_handles[-1])
    return driver.current_window_handle


def _open_target_tab(driver: webdriver.Chrome, target_url: str) -> str:
    handle = _open_blank_tab(driver)
    driver.switch_to.window(handle)
    driver.get(target_url)
    return driver.current_window_handle


def _navigate_tab(driver: webdriver.Chrome, handle: str, target_url: str) -> str:
    driver.switch_to.window(handle)
    driver.get(target_url)
    return driver.current_window_handle


def _find_matching_handles(
    driver: webdriver.Chrome, url_prefixes: Tuple[str, ...]
) -> List[str]:
    matches: List[str] = []
    original_handle = None
    try:
        original_handle = driver.current_window_handle
    except Exception:
        original_handle = None

    for handle in _window_handles(driver):
        current = _current_url_for_handle(driver, handle)
        if any(host in current for host in url_prefixes):
            matches.append(handle)

    if original_handle:
        _switch_to_handle(driver, original_handle)
    return matches


def _blank_tab_handles(driver: webdriver.Chrome) -> List[str]:
    matches: List[str] = []
    original_handle = None
    try:
        original_handle = driver.current_window_handle
    except Exception:
        original_handle = None

    for handle in _window_handles(driver):
        current = _current_url_for_handle(driver, handle)
        if _is_blank_tab_url(current):
            matches.append(handle)

    if original_handle:
        _switch_to_handle(driver, original_handle)
    return matches


def find_tab_handle(
    driver: webdriver.Chrome, url_prefixes: Tuple[str, ...]
) -> Optional[str]:
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        current = driver.current_url
        if any(host in current for host in url_prefixes):
            return handle
    return None


def inspect_seek_and_chatgpt_tabs(driver: webdriver.Chrome) -> Tuple[List[str], List[str], List[str]]:
    seek_matches = _find_matching_handles(driver, SEEK_HOSTS)
    chatgpt_matches = _find_matching_handles(driver, CHATGPT_HOSTS)
    blank_matches = _blank_tab_handles(driver)
    return seek_matches, chatgpt_matches, blank_matches


def describe_tab_urls(driver: webdriver.Chrome) -> List[str]:
    rows: List[str] = []
    original_handle = None
    try:
        original_handle = driver.current_window_handle
    except Exception:
        original_handle = None
    for handle in _window_handles(driver):
        current = _current_url_for_handle(driver, handle)
        rows.append(f"{handle}: {current or '(blank)'}")
    if original_handle:
        _switch_to_handle(driver, original_handle)
    return rows


def ensure_chatgpt(driver: webdriver.Chrome, config: Config) -> str:
    handle = find_tab_handle(driver, CHATGPT_HOSTS)
    if not handle:
        handle = ensure_tab(driver, CHATGPT_HOSTS, config.chatgpt_url)
    setattr(driver, "_jobfinder_chatgpt_handle", handle)
    return handle


def ensure_seek(driver: webdriver.Chrome, config: Config) -> str:
    handle = find_tab_handle(driver, SEEK_HOSTS)
    if not handle:
        handle = ensure_tab(driver, SEEK_HOSTS, config.seek_url)
    setattr(driver, "_jobfinder_seek_handle", handle)
    return handle


def ensure_seek_and_chatgpt_tabs(driver: webdriver.Chrome, config: Config) -> Tuple[str, str]:
    seek_matches, chatgpt_matches, _ = inspect_seek_and_chatgpt_tabs(driver)

    if seek_matches and chatgpt_matches:
        seek_handle = seek_matches[0]
        chatgpt_handle = chatgpt_matches[0]
        setattr(driver, "_jobfinder_seek_handle", seek_handle)
        setattr(driver, "_jobfinder_chatgpt_handle", chatgpt_handle)
        return seek_handle, chatgpt_handle

    blank_handles = list(_blank_tab_handles(driver))

    if seek_matches:
        seek_handle = seek_matches[0]
    elif blank_handles:
        seek_handle = _navigate_tab(driver, blank_handles[0], config.seek_url or "https://www.seek.com.au/")
    else:
        seek_handle = _open_target_tab(driver, config.seek_url or "https://www.seek.com.au/")

    _, chatgpt_matches, blank_handles = inspect_seek_and_chatgpt_tabs(driver)
    remaining_blank_handles = [handle for handle in blank_handles if handle != seek_handle]
    if chatgpt_matches:
        chatgpt_handle = chatgpt_matches[0]
    elif not seek_matches:
        chatgpt_handle = _open_target_tab(driver, config.chatgpt_url or "https://chat.openai.com/")
    elif remaining_blank_handles:
        chatgpt_handle = _navigate_tab(
            driver, remaining_blank_handles[0], config.chatgpt_url or "https://chat.openai.com/"
        )
    else:
        chatgpt_handle = _open_target_tab(driver, config.chatgpt_url or "https://chat.openai.com/")

    if seek_handle == chatgpt_handle:
        chatgpt_handle = _open_target_tab(driver, config.chatgpt_url or "https://chat.openai.com/")

    for blank_handle in _blank_tab_handles(driver):
        if blank_handle in {seek_handle, chatgpt_handle}:
            continue
        try:
            driver.switch_to.window(blank_handle)
            driver.close()
        except Exception:
            pass

    setattr(driver, "_jobfinder_seek_handle", seek_handle)
    setattr(driver, "_jobfinder_chatgpt_handle", chatgpt_handle)
    return seek_handle, chatgpt_handle


def _document_ready(driver: webdriver.Chrome) -> bool:
    try:
        return driver.execute_script("return document.readyState") == "complete"
    except Exception:
        return False


def _chatgpt_prompt_available(driver: webdriver.Chrome) -> bool:
    selectors = [
        (By.ID, "prompt-textarea"),
        (By.CSS_SELECTOR, "textarea[data-testid='prompt-textarea']"),
        (By.CSS_SELECTOR, "[contenteditable='true'][data-testid='prompt-textarea']"),
        (By.CSS_SELECTOR, "[contenteditable='true'][id='prompt-textarea']"),
    ]
    for by, value in selectors:
        try:
            elements = driver.find_elements(by, value)
        except Exception:
            continue
        for element in elements:
            try:
                if element.is_displayed():
                    return True
            except Exception:
                continue
    return False


def is_seek_ready(driver: webdriver.Chrome, config: Config) -> bool:
    handle = find_tab_handle(driver, SEEK_HOSTS)
    if not handle:
        return False
    driver.switch_to.window(handle)
    if not _document_ready(driver):
        return False
    current_url = (driver.current_url or "").lower()
    if not any(host in current_url for host in SEEK_HOSTS):
        return False
    return bool(driver.find_elements(By.TAG_NAME, "body"))


def is_chatgpt_ready(driver: webdriver.Chrome, config: Config) -> bool:
    handle = find_tab_handle(driver, CHATGPT_HOSTS)
    if not handle:
        return False
    driver.switch_to.window(handle)
    if not _document_ready(driver):
        return False
    current_url = (driver.current_url or "").lower()
    if not any(host in current_url for host in CHATGPT_HOSTS):
        return False
    return _chatgpt_prompt_available(driver)


def wait_for_seek_and_chatgpt_ready(
    driver: webdriver.Chrome,
    config: Config,
    timeout: int = 300,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    start = time.time()
    last_log_bucket = -1
    while time.time() - start < timeout:
        try:
            seek_matches, chatgpt_matches, _ = inspect_seek_and_chatgpt_tabs(driver)
            if seek_matches and chatgpt_matches and seek_matches[0] != chatgpt_matches[0]:
                _log(log, "Confirmed separate Seek and ChatGPT tabs.")
                return True
        except Exception:
            pass

        elapsed = int(time.time() - start)
        log_bucket = elapsed // 15
        if log_bucket != last_log_bucket:
            last_log_bucket = log_bucket
            _log(log, "Waiting for separate Seek and ChatGPT tabs...")
            for row in describe_tab_urls(driver):
                _log(log, f"Tab state: {row}")
        time.sleep(2)
    return False


def _window_handles(driver: webdriver.Chrome) -> List[str]:
    try:
        return list(driver.window_handles)
    except Exception:
        return []


def _switch_to_handle(driver: webdriver.Chrome, handle: Optional[str]) -> bool:
    if not handle:
        return False
    if handle not in _window_handles(driver):
        return False
    try:
        driver.switch_to.window(handle)
        return True
    except Exception:
        return False


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _find_chat_link_by_title(
    driver: webdriver.Chrome, chat_title: str
) -> Optional[Any]:
    expected = _normalize_ws(chat_title)
    if not expected:
        return None

    selectors = [
        "nav a",
        "a[href*='/c/']",
        "a[href*='/g/']",
        "[data-testid*='conversation']",
    ]
    seen = set()
    for selector in selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            continue
        for element in elements:
            element_id = element.id
            if element_id in seen:
                continue
            seen.add(element_id)
            text = _normalize_ws(element.text or "")
            if text == expected or expected in text:
                return element
    return None


def clear_chatgpt_draft(
    driver: webdriver.Chrome,
    config: Config,
    timeout: int = 30,
    log: Optional[Callable[[str], None]] = None,
) -> bool:
    chatgpt_handle = ensure_chatgpt(driver, config)
    driver.switch_to.window(chatgpt_handle)
    wait = WebDriverWait(driver, timeout)

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    except Exception:
        return False

    textarea = wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))
    driver.execute_script(
        """
        const el = arguments[0];
        el.focus();
        if (el.isContentEditable) {
            el.textContent = '';
            el.innerHTML = '';
        } else {
            el.value = '';
        }
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        textarea,
    )
    time.sleep(0.5)

    try:
        current_text = textarea.get_attribute("value") or textarea.text or ""
    except Exception:
        current_text = ""

    cleared = not current_text.strip()
    if cleared:
        _log(log, "已清空 ChatGPT 输入框草稿。")
    return cleared


def clear_chatgpt_draft_via_debugger(
    config: Config,
    log: Optional[Callable[[str], None]] = None,
    attempts: int = 3,
    delay_sec: int = 3,
) -> bool:
    last_error: Optional[Exception] = None
    for _ in range(attempts):
        driver: Optional[webdriver.Chrome] = None
        try:
            driver = connect_driver(config)
            if clear_chatgpt_draft(driver, config, log=log):
                return True
        except Exception as exc:
            last_error = exc
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
        time.sleep(delay_sec)

    if last_error:
        _log(log, f"未能清空 ChatGPT 输入框: {last_error}")
    return False




def collect_job_links(driver: webdriver.Chrome, limit: Optional[int]) -> List[str]:
    candidates = driver.find_elements(By.CSS_SELECTOR, "a[data-automation='jobTitle']")
    if not candidates:
        candidates = driver.find_elements(By.CSS_SELECTOR, "a[href*='/job/']")
    links: List[str] = []
    for el in candidates:
        href = el.get_attribute("href")
        if not href or "/job/" not in href:
            continue
        if href not in links:
            links.append(href)
        if limit and len(links) >= limit:
            break
    return links


def _click_new_to_you_filter(driver: webdriver.Chrome) -> bool:
    selectors = [
        (By.ID, "new-to-you-filter-text"),
        (By.CSS_SELECTOR, "[aria-describedby='new-to-you-tooltip-renderer']"),
        (By.CSS_SELECTOR, "[data-automation='newToYouJobsCountTabletAndDesktop']"),
        (By.XPATH, "//*[contains(., 'New to you') and (self::div or self::span)]"),
    ]
    wait = WebDriverWait(driver, 10)
    for by, value in selectors:
        try:
            el = wait.until(EC.presence_of_element_located((by, value)))
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", el
            )
            time.sleep(0.8)
            wait.until(EC.element_to_be_clickable((by, value)))
            try:
                el.click()
            except Exception:
                driver.execute_script("arguments[0].click();", el)
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def _click_all_jobs_filter(driver: webdriver.Chrome) -> bool:
    for selector in [
        "[data-automation='totalJobsMessage']",
        "div[data-automation='totalJobsMessage']",
    ]:
        try:
            el = driver.find_element(By.CSS_SELECTOR, selector)
            parent = el
            for _ in range(3):
                try:
                    parent = driver.execute_script(
                        "return arguments[0].parentElement;", parent
                    )
                    if parent:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center'});",
                            parent,
                        )
                        time.sleep(0.3)
                        parent.click()
                        time.sleep(2)
                        return True
                except Exception:
                    break
            el.click()
            time.sleep(2)
            return True
        except Exception:
            continue
    return False


def go_to_next_page(driver: webdriver.Chrome) -> bool:
    for selector in [
        "a[aria-label='Next']",
        "a[aria-label='下一页']",
        "button[aria-label='Next']",
        "button[aria-label='下一页']",
        "a[data-automation='page-next']",
        "button[data-automation='page-next']",
    ]:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            button = elements[0]
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", button
            )
            time.sleep(0.5)
            try:
                button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", button)
            time.sleep(2)
            return True
    return False


def _has_resume_content(resume_sections: Dict[str, Any]) -> bool:
    """True only when ChatGPT returned real resume body content.

    ``resume_sections`` always carries the candidate's name/contact (filled in
    by ``_normalize_candidate_identity``), so its mere presence is not enough to
    justify a resume PDF. Require an actual summary, experience, education, or
    skills entry — otherwise a skipped/zero-score job would still emit an empty
    header-only resume.
    """
    if not resume_sections:
        return False
    if str(resume_sections.get("professional_summary", "") or "").strip():
        return True
    for key in ("experience", "education", "skills"):
        if resume_sections.get(key):
            return True
    return False


def export_pdfs_for_job(
    driver: webdriver.Chrome,
    config: Config,
    payload: Dict[str, Any],
    job_id: str,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    output_dir = config.pdf_output_dir.strip() or "pdf_output"
    job_dir = os.path.join(output_dir, str(job_id))
    os.makedirs(job_dir, exist_ok=True)

    other = payload.get("other", {})
    notes = payload.get("notes", {})
    resume_sections = other.get("resume_sections") or {}
    resume_text = extract_text_value(notes.get("Resume"))
    cover_text = extract_text_value(
        other.get("cover_letter", other.get("Cover Letter", notes.get("Cover Letter")))
    )
    cover_text = _normalize_cover_letter_body(cover_text, config)

    safe_job_title = sanitize_filename(payload.get("job_meta", {}).get("job_title", ""))
    safe_company = sanitize_filename(payload.get("job_meta", {}).get("company", ""))
    safe_name = sanitize_filename(resume_sections.get("name") or config.user_name)
    base_name = " - ".join(part for part in [safe_job_title, safe_company, safe_name] if part)
    if not base_name:
        base_name = str(job_id)

    if resume_text or _has_resume_content(resume_sections):
        resume_pdf = os.path.join(job_dir, f"{base_name} - resume.pdf")
        render_text_pdf(driver, config, "Resume", resume_text, resume_pdf, resume_sections)
        _log(log, f"已导出简历 PDF: {resume_pdf}")
    else:
        _log(log, "跳过简历 PDF：ChatGPT 未生成简历内容（可能该职位被评为不匹配）。")

    if cover_text:
        cover_pdf = os.path.join(job_dir, f"{base_name} - cover-letter.pdf")
        render_text_pdf(driver, config, "Cover Letter", cover_text, cover_pdf, resume_sections)
        _log(log, f"已导出求职信 PDF: {cover_pdf}")
    else:
        _log(log, "跳过求职信 PDF：ChatGPT 未生成求职信内容（可能该职位被评为不匹配）。")


def extract_text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item)
    return str(value)


def _display_title_case(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        return ""
    if any(ch.isupper() for ch in text[1:]):
        return text
    return text.title()


def _normalize_position_text(value: str) -> str:
    text = " ".join((value or "").strip().split())
    if not text:
        return ""
    if any(ch.isupper() for ch in text[1:]):
        return text
    return text.title()


def _normalize_cover_letter_body(cover_text: str, config: Config) -> str:
    text = (cover_text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""

    candidate_bits = [
        str(getattr(config, "user_name", "") or "").strip().lower(),
        str(getattr(config, "user_address", "") or "").strip().lower(),
        str(getattr(config, "user_phone", "") or "").strip().lower(),
        str(getattr(config, "user_email", "") or "").strip().lower(),
    ]
    candidate_bits = [bit for bit in candidate_bits if bit]

    lines = [line.strip() for line in text.split("\n")]
    kept_lines: List[str] = []
    salutation_seen = False
    for line in lines:
        if not line:
            kept_lines.append("")
            continue
        lower = line.lower()
        if not salutation_seen and (lower.startswith("dear ") or lower.startswith("to ")):
            salutation_seen = True
            kept_lines.append(line)
            continue
        if not salutation_seen and any(bit == lower for bit in candidate_bits):
            continue
        if not salutation_seen and "@" in line:
            continue
        if not salutation_seen and re.fullmatch(r"[\+\d\s\-\(\)]{7,}", line):
            continue
        kept_lines.append(line)

    while kept_lines and not kept_lines[0]:
        kept_lines.pop(0)
    while kept_lines and not kept_lines[-1]:
        kept_lines.pop()

    closing_patterns = (
        "kind regards",
        "regards",
        "best regards",
        "sincerely",
        "yours sincerely",
        "yours faithfully",
        "thank you",
    )
    while kept_lines:
        last = kept_lines[-1].strip().lower()
        if not last:
            kept_lines.pop()
            continue
        if last in closing_patterns:
            kept_lines.pop()
            continue
        if candidate_bits and any(last == bit for bit in candidate_bits):
            kept_lines.pop()
            continue
        break

    normalized = "\n".join(kept_lines).strip()
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def build_header_context(resume_sections: Dict[str, Any], config: Config) -> Dict[str, str]:
    return {
        "name": _display_title_case(str(resume_sections.get("name", "") or "")),
        "position": _normalize_position_text(str(resume_sections.get("position", "") or "")),
        "address": str(config.user_address or ""),
        "phone": str(resume_sections.get("phone", "") or config.user_phone or ""),
        "email": str(resume_sections.get("email", "") or config.user_email or ""),
    }


def build_resume_sections_html(resume_sections: Dict[str, Any]) -> str:
    summary = escape(str(resume_sections.get("professional_summary", "") or "")).replace("\n", "<br>")
    experience = resume_sections.get("experience") or []
    education = resume_sections.get("education") or []
    skills = resume_sections.get("skills") or []

    experience_html = ""
    for item in experience:
        bullets = item.get("bullets") or []
        bullets_html = "".join(
            f"<li>{escape(str(b))}</li>" for b in bullets if b
        )
        experience_html += f"""
        <div class="experience-item">
            <div class="experience-header">
                <div class="company-location">
                    <span class="company-name">{escape(str(item.get("company", "")))}</span>
                    <span class="location"> | {escape(str(item.get("location", "")))}</span>
                </div>
                <span class="date">{escape(str(item.get("date", "")))}</span>
            </div>
            <div class="role">{escape(str(item.get("role", "")))}</div>
            <ul class="responsibilities">{bullets_html}</ul>
        </div>
        """

    education_html = ""
    for item in education:
        education_html += f"""
        <div class="education-item">
            <div class="institution-location">
                <span class="institution">{escape(str(item.get("institution", "")))}</span>
                <span class="location"> | {escape(str(item.get("location", "")))}</span>
            </div>
            <div class="degree">{escape(str(item.get("degree", "")))}</div>
        </div>
        """

    skills_html = "".join(
        f'<div class="skill-item">{escape(str(s))}</div>' for s in skills if s
    )

    return f"""
    <section class="section">
        <div class="section-header"><h3 class="section-title">Professional Summary</h3></div>
        <div class="section-content"><p class="about-text">{summary}</p></div>
    </section>
    <section class="section">
        <div class="section-header"><h3 class="section-title">Work Experience</h3></div>
        <div class="section-content"><div class="experience-list">{experience_html}</div></div>
    </section>
    <section class="section">
        <div class="section-header"><h3 class="section-title">Education</h3></div>
        <div class="section-content"><div class="education-list">{education_html}</div></div>
    </section>
    <section class="section">
        <div class="section-header"><h3 class="section-title">Skills</h3></div>
        <div class="section-content"><div class="skills-grid">{skills_html}</div></div>
    </section>
    """


def build_cover_section_html(title: str, html_body: str) -> str:
    if title == "Resume":
        return ""
    return f"""
    <section class="section">
        <div class="section-content">
            <div class="content-block">{html_body}</div>
        </div>
    </section>
    """


def build_cover_contact_html(header: Dict[str, str]) -> str:
    """Build the right-side contact column for the minimal cover letter template.

    Only fields with a value are rendered, so an empty address/phone/email does
    not leave a dangling icon.
    """
    rows = []
    for key in ("address", "email", "phone"):
        value = str(header.get(key, "") or "").strip()
        if not value:
            continue
        icon = _CONTACT_ICON_SVGS["address" if key == "address" else key]
        rows.append(
            '<div class="cl-contact-item">'
            f'<span class="cl-icon">{icon}</span>'
            f"<span>{escape(value)}</span>"
            "</div>"
        )
    return "\n".join(rows)


def build_cover_body_html(body: str) -> str:
    """Render the cover letter body as paragraphs, bolding the salutation line."""
    text = (body or "").strip()
    if not text:
        return ""
    blocks = re.split(r"\n\s*\n", text)
    parts = []
    first_block = True
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        inner = escape(block).replace("\n", "<br>")
        lower = block.lower()
        if first_block and (lower.startswith("dear ") or lower.startswith("to ")):
            parts.append(f'<p class="greeting">{inner}</p>')
        else:
            parts.append(f'<p class="cover-paragraph">{inner}</p>')
        first_block = False
    return "\n".join(parts)


def _cover_letter_signature_text(config: Config) -> str:
    display_name = _display_title_case(str(getattr(config, "user_name", "") or "").strip())
    if not display_name:
        return ""
    return f"\n\nKind regards,\n{display_name}"


def sanitize_filename(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    value = re.sub(r"[‐‑‒–—―]", "-", value)
    value = re.sub(r"[\\/:*?\"<>|]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _resolve_cover_letter_template_path(config: Config) -> str:
    """Map the selected cover-letter design to its HTML template path."""
    design = str(getattr(config, "cover_letter_design", "") or "").strip() or DEFAULT_COVER_LETTER_DESIGN
    path = COVER_LETTER_DESIGN_TEMPLATES.get(design)
    if not path:
        path = COVER_LETTER_DESIGN_TEMPLATES.get(DEFAULT_COVER_LETTER_DESIGN, COVER_LETTER_TEMPLATE_PATH)
    return path


def _build_cover_letter_html(
    config: Config,
    body: str,
    resume_sections: Dict[str, Any],
    css_text: str,
) -> str:
    """Build the cover letter HTML for the design selected in settings.

    The minimal template (detected by its dedicated placeholders) gets the
    light layout with a contact column and a typed signature. Any other
    template (e.g. Navy Gold) is rendered through the shared header / cover
    section logic with the classic appended signature line.
    """
    header = build_header_context(resume_sections, config)
    signature_name = _display_title_case(
        str(getattr(config, "user_name", "") or "").strip()
    ) or header.get("name", "")

    template_path = _resolve_cover_letter_template_path(config)
    if template_path and os.path.exists(template_path):
        template = Path(template_path).read_text(encoding="utf-8")

        if "{{SIGNATURE_NAME}}" in template or "{{CONTACT_BLOCK}}" in template:
            return (
                template.replace("{{HEADER_NAME}}", escape(header["name"] or signature_name))
                .replace("{{HEADER_TITLE}}", escape(header["position"]))
                .replace("{{CONTACT_BLOCK}}", build_cover_contact_html(header))
                .replace("{{COVER_SECTION}}", build_cover_body_html(body))
                .replace("{{SIGNATURE_NAME}}", escape(signature_name))
                .replace("{{CSS}}", css_text)
            )

        signed_body = f"{(body or '').rstrip()}{_cover_letter_signature_text(config)}"
        html_body = escape(signed_body).replace("\n", "<br>")
        return (
            template.replace("{{HEADER_NAME}}", escape(header["name"]))
            .replace("{{HEADER_TITLE}}", escape(header["position"]))
            .replace("{{HEADER_ADDRESS}}", escape(header["address"]))
            .replace("{{HEADER_PHONE}}", escape(header["phone"]))
            .replace("{{HEADER_EMAIL}}", escape(header["email"]))
            .replace("{{RESUME_SECTIONS}}", "")
            .replace("{{COVER_SECTION}}", build_cover_section_html("Cover Letter", html_body))
            .replace("{{CONTENT}}", html_body)
            .replace("{{BODY}}", html_body)
            .replace("{{CSS}}", css_text)
        )

    signed_body = f"{(body or '').rstrip()}{_cover_letter_signature_text(config)}"
    html_body = escape(signed_body).replace("\n", "<br>")
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
{css_text}
  </style>
</head>
<body>
  <div class="document">
    <div class="content">{html_body}</div>
  </div>
</body>
</html>
"""


def render_text_pdf(
    driver: webdriver.Chrome,
    config: Config,
    title: str,
    body: str,
    output_path: str,
    resume_sections: Dict[str, Any],
) -> None:
    css_text = ""
    if config.pdf_css_path and os.path.exists(config.pdf_css_path):
        with open(config.pdf_css_path, "r", encoding="utf-8") as f:
            css_text = f.read()

    is_cover_letter = title != "Resume"

    # Cover letters use the design selected in settings (default: the minimal
    # light layout). Resumes keep using the configured resume template.
    if is_cover_letter:
        html = _build_cover_letter_html(config, body, resume_sections, css_text)
        _render_html_to_pdf(driver, title, html, output_path)
        return

    html_body = escape(body).replace("\n", "<br>")
    template_path = config.pdf_template_path.strip()
    if template_path:
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"找不到 HTML 模板: {template_path}")
        template = Path(template_path).read_text(encoding="utf-8")
        if (
            "{{RESUME_SECTIONS}}" not in template
            and "{{COVER_SECTION}}" not in template
            and "{{CONTENT}}" not in template
            and "{{BODY}}" not in template
        ):
            raise ValueError("HTML 模板缺少内容占位符。")
        header = build_header_context(resume_sections, config)
        resume_sections_html = build_resume_sections_html(resume_sections)
        cover_section_html = build_cover_section_html(title, html_body)
        html = (
            template.replace("{{HEADER_NAME}}", escape(header["name"]))
            .replace("{{HEADER_TITLE}}", escape(header["position"]))
            .replace("{{HEADER_ADDRESS}}", escape(header["address"]))
            .replace("{{HEADER_PHONE}}", escape(header["phone"]))
            .replace("{{HEADER_EMAIL}}", escape(header["email"]))
            .replace("{{RESUME_SECTIONS}}", resume_sections_html if title == "Resume" else "")
            .replace("{{COVER_SECTION}}", cover_section_html if title != "Resume" else "")
            .replace("{{CONTENT}}", html_body)
            .replace("{{BODY}}", html_body)
            .replace("{{CSS}}", css_text)
        )
    else:
        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <style>
{css_text}
  </style>
</head>
<body>
  <div class="document">
    <h1>{escape(title)}</h1>
    <div class="content">{html_body}</div>
  </div>
</body>
</html>
"""
    _render_html_to_pdf(driver, title, html, output_path)


def _render_html_to_pdf(
    driver: webdriver.Chrome,
    title: str,
    html: str,
    output_path: str,
) -> None:
    temp_dir = Path("pdf_output") / "tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_file = temp_dir / f"{title.lower().replace(' ', '_')}.html"
    temp_file.write_text(html, encoding="utf-8")

    original_handle = driver.current_window_handle
    existing_handles = list(driver.window_handles)
    seek_handle = getattr(driver, "_jobfinder_seek_handle", None)
    chatgpt_handle = getattr(driver, "_jobfinder_chatgpt_handle", None)

    # 新开临时 tab 用于渲染 PDF（避免复用现有 tab）
    try:
        driver.switch_to.new_window("tab")
    except Exception:
        driver.execute_script("window.open('about:blank', '_blank');")
        time.sleep(0.2)
    pdf_handle = driver.current_window_handle

    try:
        if not pdf_handle or pdf_handle not in driver.window_handles:
            raise RuntimeError("无法打开 PDF 渲染标签页。")
        driver.switch_to.window(pdf_handle)
        driver.get(temp_file.resolve().as_uri())
        time.sleep(1)

        pdf_data = driver.execute_cdp_cmd(
            "Page.printToPDF",
            {
                "printBackground": True,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
            },
        )
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(pdf_data["data"]))
    finally:
        # 只关闭这次新开的 PDF tab，且不要关 Seek/ChatGPT
        try:
            handles = list(driver.window_handles)
            if (
                pdf_handle in handles
                and pdf_handle not in {seek_handle, chatgpt_handle}
                and len(handles) > 1
            ):
                driver.switch_to.window(pdf_handle)
                driver.close()
        except Exception:
            pass

        # 关闭后再切回原 tab，避免焦点跳到 Seek
        try:
            handles = list(driver.window_handles)
        except Exception:
            handles = []

        preferred_handle = None
        if original_handle in handles:
            preferred_handle = original_handle
        elif chatgpt_handle in handles:
            preferred_handle = chatgpt_handle
        elif seek_handle in handles:
            preferred_handle = seek_handle
        elif handles:
            preferred_handle = handles[0]

        if preferred_handle:
            try:
                driver.switch_to.window(preferred_handle)
            except Exception:
                pass


def extract_text(driver: webdriver.Chrome, selectors: List[str]) -> str:
    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            text = elements[0].text.strip()
            if text:
                return text
    return ""


def extract_job_meta(driver: webdriver.Chrome) -> Dict[str, str]:
    title = extract_text(driver, ["h1[data-automation='job-detail-title']", "h1"])
    company = extract_text(
        driver, ["span[data-automation='advertiser-name']", "a[data-automation='advertiser-name']"]
    )
    location = extract_text(
        driver, ["span[data-automation='job-detail-location']", "span[data-automation='jobDetailLocation']"]
    )
    return {"job_title": title, "company": company, "location": location}


def extract_job_description(driver: webdriver.Chrome) -> str:
    return extract_text(
        driver,
        [
            "div[data-automation='jobAdDetails']",
            "section[data-automation='jobAdDetails']",
            "div[data-automation='job-detail-description']",
            "main",
            "body",
        ],
    )


def apply_seek_search(driver: webdriver.Chrome, config: Config) -> bool:
    keyword = config.keyword or ""
    location = config.job_location or ""

    keyword_input = None
    location_input = None

    for selector in [
        "input[placeholder*='job']",
        "input[aria-label*='job']",
        "input[name='keywords']",
        "input[data-automation='keywordsField']",
    ]:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            keyword_input = elements[0]
            break

    for selector in [
        "input[placeholder*='Where']",
        "input[aria-label*='Where']",
        "input[name='where']",
        "input[data-automation='whereField']",
    ]:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        if elements:
            location_input = elements[0]
            break

    if keyword_input:
        keyword_input.clear()
        keyword_input.send_keys(keyword)
    if location_input:
        location_input.clear()
        location_input.send_keys(location)

    if not keyword_input and not location_input:
        return False

    for selector in [
        "button[data-automation='searchButton']",
        "button[type='submit']",
    ]:
        buttons = driver.find_elements(By.CSS_SELECTOR, selector)
        if buttons:
            button = buttons[0]
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", button
            )
            time.sleep(0.5)
            try:
                button.click()
            except Exception:
                driver.execute_script("arguments[0].click();", button)
            return True
    return False


def _switch_to_instant_mode(
    driver: webdriver.Chrome,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    """尝试将 ChatGPT 切换到 Instant/Fast 模式，避免 Think 模式变慢。"""
    try:
        btns = driver.find_elements(
            By.CSS_SELECTOR, "button[data-testid='model-switcher-dropdown-button']"
        )
        if not btns:
            return
        btn = btns[0]
        label = (btn.get_attribute("aria-label") or btn.text or "").lower()
        if "instant" in label or "fast" in label:
            _log(log, "ChatGPT 已是 Instant/Fast 模式。")
            return
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
        time.sleep(0.3)
        btn.click()
        time.sleep(0.8)
        for sel in [
            "[data-radix-menu-content][data-state='open']",
            "[role='menu']",
            "[data-state='open']",
        ]:
            menus = driver.find_elements(By.CSS_SELECTOR, sel)
            for menu in menus:
                for variant in ("instant", "fast"):
                    items = menu.find_elements(
                        By.CSS_SELECTOR,
                        f"[role='menuitem'][data-testid*='{variant}'], "
                        f"[role='option'][data-testid*='{variant}']",
                    )
                    for el in items:
                        if variant in (el.text or "").lower():
                            el.click()
                            _log(log, f"已切换到 {variant} 模式。")
                            return
                    for el in menu.find_elements(
                        By.CSS_SELECTOR, "[role='menuitem'], [role='option']"
                    ):
                        if variant in (el.text or "").lower():
                            el.click()
                            _log(log, f"已切换到 {variant} 模式。")
                            return
    except Exception:
        pass


def send_prompt(
    driver: webdriver.Chrome,
    config: Config,
    prompt: str,
    timeout: int = 180,
    log: Optional[Callable[[str], None]] = None,
) -> str:
    def _is_local_driver_timeout(exc: Exception) -> bool:
        text = str(exc)
        return (
            "HTTPConnectionPool" in text
            or "Read timed out" in text
            or "read timeout" in text.lower()
            or "localhost" in text.lower()
        )

    def _refresh_chatgpt_after_timeout() -> None:
        chatgpt_handle = ensure_chatgpt(driver, config)
        driver.switch_to.window(chatgpt_handle)
        _log(log, "Detected local driver timeout. Refreshing ChatGPT and retrying...")
        try:
            driver.refresh()
        except Exception:
            driver.get(config.chatgpt_url or "https://chat.openai.com/")
        time.sleep(6)

    def get_assistant_texts() -> List[str]:
        try:
            return driver.execute_script(
                """
                var els = document.querySelectorAll('[data-message-author-role="assistant"]');
                if (!els.length) els = document.querySelectorAll('div[data-message-author-role="assistant"]');
                return Array.from(els).map(el => (el.textContent || '').trim()).filter(s => s.length > 0);
                """
            ) or []
        except Exception:
            items = driver.find_elements(
                By.CSS_SELECTOR, "div[data-message-author-role='assistant']"
            )
            return [item.text.strip() for item in items if item.text.strip()]

    attempts = 0
    last_error: Optional[Exception] = None

    while attempts < 2:
        attempts += 1
        try:
            chatgpt_handle = ensure_chatgpt(driver, config)
            driver.switch_to.window(chatgpt_handle)
            wait = WebDriverWait(driver, timeout)

            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "nav")))
            except Exception:
                pass

            chat_title = (config.chatgpt_chat_title or "").strip()
            chat_link = _find_chat_link_by_title(driver, chat_title) if chat_title else None
            if chat_link:
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", chat_link
                )
                time.sleep(0.5)
                try:
                    chat_link.click()
                except Exception:
                    driver.execute_script("arguments[0].click();", chat_link)

            time.sleep(2)
            _switch_to_instant_mode(driver, log)
            time.sleep(3)
            clear_chatgpt_draft(driver, config, timeout=timeout, log=log)
            textarea = wait.until(EC.presence_of_element_located((By.ID, "prompt-textarea")))
            textarea.click()
            driver.execute_script(
                """
                const el = arguments[0];
                const text = arguments[1];
                el.focus();
                if (el.isContentEditable) {
                    el.textContent = text;
                } else {
                    el.value = text;
                }
                el.dispatchEvent(new Event('input', { bubbles: true }));
                """,
                textarea,
                prompt,
            )
            time.sleep(1)
            try:
                current_text = textarea.get_attribute("value") or textarea.text or ""
            except Exception:
                current_text = ""
            if len(current_text.strip()) < min(80, len(prompt.strip())):
                driver.execute_script(
                    """
                    const el = arguments[0];
                    const text = arguments[1];
                    el.focus();
                    if (el.isContentEditable) {
                        el.textContent = text;
                    } else {
                        el.value = text;
                    }
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    """,
                    textarea,
                    prompt,
                )
            time.sleep(2)
            count_before_send = len(get_assistant_texts())
            textarea.send_keys(Keys.ENTER)

            existing_texts = get_assistant_texts()
            last_text_before = existing_texts[-1] if existing_texts else ""

            def _stop_button_visible() -> bool:
                for sel in [
                    "button[aria-label='Stop generating']",
                    "button[data-testid='stop-button']",
                ]:
                    if driver.find_elements(By.CSS_SELECTOR, sel):
                        return True
                return False

            _log(log, "Waiting for ChatGPT reply...")
            start_time = time.time()
            last_log_time = 0.0
            while time.time() - start_time < timeout:
                elapsed = time.time() - start_time
                if elapsed >= 30 and elapsed - last_log_time >= 30:
                    _log(log, f"Still waiting... ({int(elapsed)} sec)")
                    last_log_time = elapsed
                if _stop_button_visible():
                    _log(log, "Detected ChatGPT generating...")
                    break
                current_texts = get_assistant_texts()
                if len(current_texts) > count_before_send:
                    _log(log, "Detected new reply, waiting for completion...")
                    break
                if current_texts and current_texts[-1] != last_text_before:
                    _log(log, "Detected reply content change, waiting for completion...")
                    break
                time.sleep(1)
            else:
                last_error = TimeoutException("ChatGPT did not return a reply within the timeout.")
                if attempts < 2:
                    _log(log, "Timed out waiting, refreshing page and retrying...")
                    driver.refresh()
                    time.sleep(6)
                    continue
                raise last_error

            last_text = ""
            stable_count = 0
            while time.time() - start_time < timeout:
                stop_buttons = (
                    driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Stop generating']")
                    or driver.find_elements(By.CSS_SELECTOR, "button[data-testid='stop-button']")
                )
                current_texts = get_assistant_texts()
                if current_texts:
                    current_text = current_texts[-1]
                    if current_text and current_text == last_text:
                        stable_count += 1
                    else:
                        stable_count = 0
                    last_text = current_text
                if not stop_buttons and stable_count >= 2:
                    break
                time.sleep(1)

            responses = get_assistant_texts()
            if not responses:
                last_error = TimeoutException("No assistant response found.")
                if attempts < 2:
                    _log(log, "No reply detected, refreshing page and retrying...")
                    driver.refresh()
                    time.sleep(6)
                    continue
                raise last_error
            return responses[-1].strip()
        except Exception as exc:
            last_error = exc
            if attempts < 2 and _is_local_driver_timeout(exc):
                _refresh_chatgpt_after_timeout()
                continue
            raise

    if last_error:
        raise last_error
    raise TimeoutException("ChatGPT processing failed.")


def _process_single_job(
    driver: webdriver.Chrome,
    config: Config,
    job_ids: set,
    job_url: str,
    job_meta: Dict[str, Any],
    job_description: str,
    log: Optional[Callable[[str], None]],
    runs_left: Optional[int],
    seek_handle: str,
    review_single_cover_letter: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[int]:
    job_id = extract_job_id(job_url) or "?"
    title = job_meta.get("job_title", "") or "无标题"
    _log(log, f"发送 ChatGPT: {job_id} - {title}")

    try:
        prompt = build_prompt(job_description, config)
        timeout = 180
        attempts = 0
        while attempts < 2:
            response_text = send_prompt(driver, config, prompt, timeout=timeout, log=log)
            try:
                payload = extract_json_from_text(response_text)
                payload = _normalize_candidate_identity(payload, config)
                break
            except Exception as exc:
                attempts += 1
                if attempts >= 2:
                    raise exc
                _log(log, "JSON 解析失败，已请求 ChatGPT 重新输出...")
                prompt = f"{prompt}\n\nIMPORTANT: Return ONLY a valid JSON object. No commentary."

        payload.setdefault("job_meta", {}).update(job_meta)
        if review_single_cover_letter and config.single_job_url:
            other = payload.setdefault("other", {})
            cover_key = "cover_letter" if "cover_letter" in other else "Cover Letter"
            initial_cover_text = str(other.get(cover_key, "") or "")
            edited_cover_text = review_single_cover_letter(initial_cover_text)
            if edited_cover_text is None:
                _log(log, "Cover letter review cancelled. Skipping save.")
                return runs_left
            other[cover_key] = _normalize_cover_letter_body(edited_cover_text, config)
        _log(log, "写入 Excel...")
        saved_id = append_row_to_excel(config, payload)
        job_ids.add(saved_id)
        _log(log, f"已保存: {saved_id}")
        if config.enable_local_sync and config.local_sync_path:
            sync_path = os.path.abspath(config.local_sync_path)
            os.makedirs(os.path.dirname(sync_path), exist_ok=True)
            shutil.copy2(os.path.abspath(config.output_excel), sync_path)
        if config.enable_pdf_export:
            try:
                export_pdfs_for_job(driver, config, payload, saved_id, log=log)
            except Exception as exc:
                _log(log, f"PDF 导出失败: {exc}")
        if runs_left is not None:
            runs_left -= 1
            if runs_left <= 0:
                return runs_left
    except Exception as exc:
        _log(log, f"处理失败: {exc}")
    return runs_left


def _normalize_candidate_identity(payload: Dict[str, Any], config: Config) -> Dict[str, Any]:
    other = payload.setdefault("other", {})
    resume_sections = other.setdefault("resume_sections", {})
    prior_name = str(resume_sections.get("name", "") or "").strip()

    current_name = str(getattr(config, "user_name", "") or "")
    current_address = str(getattr(config, "user_address", "") or "")
    current_phone = str(getattr(config, "user_phone", "") or "")
    current_email = str(getattr(config, "user_email", "") or "")

    resume_sections["name"] = current_name
    resume_sections["address"] = current_address
    resume_sections["phone"] = current_phone
    resume_sections["email"] = current_email
    resume_sections["name"] = _display_title_case(resume_sections["name"])
    if resume_sections.get("position"):
        resume_sections["position"] = _normalize_position_text(str(resume_sections.get("position", "")))

    cover_key = "cover_letter" if "cover_letter" in other else "Cover Letter"
    cover_text = other.get(cover_key)
    if isinstance(cover_text, str) and current_name:
        wrong_names = [prior_name, "Carl", "Carl Chen", "carl chen"]
        for wrong_name in wrong_names:
            if wrong_name and wrong_name != current_name:
                cover_text = cover_text.replace(wrong_name, current_name)
        other[cover_key] = _normalize_cover_letter_body(cover_text, config)
    elif isinstance(cover_text, str):
        other[cover_key] = _normalize_cover_letter_body(cover_text, config)

    return payload


def _process_job_links(
    driver: webdriver.Chrome,
    config: Config,
    job_ids: set,
    links: List[str],
    log: Optional[Callable[[str], None]],
    runs_left: Optional[int],
    seek_handle: str,
    return_url: str,
    skip_existing: bool = True,
    total_runs: Optional[int] = None,
    review_single_cover_letter: Optional[Callable[[str], Optional[str]]] = None,
) -> Optional[int]:
    attempt_index = 0

    for index, job_url in enumerate(links, start=1):
        job_id = extract_job_id(job_url)
        if skip_existing and job_id and job_id in job_ids:
            _log(log, f"跳过已处理: {job_id}")
            continue

        attempt_index += 1
        processed_count = (
            (total_runs - runs_left) if total_runs is not None and runs_left is not None else 0
        )
        progress_str = f"已处理 {processed_count}/{total_runs}" if total_runs else ""
        job_id_display = job_id or "(获取中)"

        _log(log, f"正在处理: {job_id_display} (尝试第 {attempt_index} 个{('，' + progress_str) if progress_str else ''})")

        driver.get(job_url)
        time.sleep(2)

        job_meta = extract_job_meta(driver)
        job_meta["job_url"] = job_url
        job_title = job_meta.get("job_title", "")

        skip_reason = should_skip_job_by_title(job_title, config)
        if skip_reason:
            _log(log, f"跳过(标题包含 '{skip_reason}'): {job_title or job_id}")
            saved_id = append_skipped_job_to_excel(config, job_meta, skip_reason)
            job_ids.add(saved_id)
            if config.enable_local_sync and config.local_sync_path:
                sync_path = os.path.abspath(config.local_sync_path)
                os.makedirs(os.path.dirname(sync_path), exist_ok=True)
                shutil.copy2(os.path.abspath(config.output_excel), sync_path)
            if _switch_to_handle(driver, seek_handle):
                driver.get(return_url)
            continue

        job_description = extract_job_description(driver)

        # 逐个发送给 ChatGPT，保证 resume 完整
        processed_count = (
            (total_runs - runs_left) if total_runs is not None and runs_left is not None else 0
        )
        progress_label = (
            f"{processed_count + 1}/{total_runs}" if total_runs else str(processed_count + 1)
        )
        _log(log, f"处理职位 ({progress_label})")
        runs_left = _process_single_job(
            driver,
            config,
            job_ids,
            job_url,
            job_meta,
            job_description,
            log,
            runs_left,
            seek_handle,
            review_single_cover_letter=review_single_cover_letter,
        )
        if runs_left is not None and runs_left <= 0:
            return runs_left

        delay_min = getattr(config, "delay_between_jobs_min_sec", 30)
        delay_max = getattr(config, "delay_between_jobs_max_sec", 90)
        if delay_min < delay_max:
            delay = random.uniform(delay_min, delay_max)
            _log(log, f"等待 {delay:.0f} 秒后继续...")
            time.sleep(delay)
        elif delay_min > 0:
            _log(log, f"等待 {delay_min} 秒后继续...")
            time.sleep(delay_min)

        if _switch_to_handle(driver, seek_handle):
            driver.get(return_url)

    return runs_left


def run_web_flow(
    config: Config,
    log: Optional[Callable[[str], None]] = None,
    include_landing_recommendations: bool = False,
    include_new_to_you: bool = False,
    review_single_cover_letter: Optional[Callable[[str], Optional[str]]] = None,
) -> None:
    job_ids = set(load_job_ids_from_excel(config.output_excel))
    runs_left = config.max_runs

    driver = connect_driver(config)
    try:
        if config.enable_local_sync and config.local_sync_pull_before_run:
            sync_path = os.path.abspath(config.local_sync_path)
            if sync_path and os.path.exists(sync_path):
                shutil.copy2(sync_path, os.path.abspath(config.output_excel))
                _log(log, f"已从同步路径更新本地 Excel: {sync_path}")

        seek_handle, _ = ensure_seek_and_chatgpt_tabs(driver, config)
        _switch_to_handle(driver, seek_handle)

        if config.single_job_url:
            _log(log, "单个 JD URL 模式，直接处理该职位...")
            driver.get(config.single_job_url)
            time.sleep(2)

            job_meta = extract_job_meta(driver)
            job_meta["job_url"] = config.single_job_url
            job_title = job_meta.get("job_title", "")
            skip_reason = should_skip_job_by_title(job_title, config)
            if skip_reason:
                _log(log, f"跳过(标题包含 '{skip_reason}'): {job_title or config.single_job_url}")
                saved_id = append_skipped_job_to_excel(config, job_meta, skip_reason)
                job_ids.add(saved_id)
                if config.enable_local_sync and config.local_sync_path:
                    sync_path = os.path.abspath(config.local_sync_path)
                    os.makedirs(os.path.dirname(sync_path), exist_ok=True)
                    shutil.copy2(os.path.abspath(config.output_excel), sync_path)
                return

            job_description = extract_job_description(driver)
            _process_single_job(
                driver,
                config,
                job_ids,
                config.single_job_url,
                job_meta,
                job_description,
                log,
                1,
                seek_handle,
                review_single_cover_letter=review_single_cover_letter,
            )
            _log(log, "单个 JD URL 已处理完成，程序结束。")
            return

        if include_landing_recommendations:
            landing_url = driver.current_url
            landing_links = collect_job_links(driver, limit=None)
            if landing_links:
                _log(log, "开始处理推荐页职位...")
                runs_left = _process_job_links(
                    driver,
                    config,
                    job_ids,
                    landing_links,
                    log,
                    runs_left,
                    seek_handle,
                    landing_url,
                    total_runs=config.max_runs,
                    review_single_cover_letter=review_single_cover_letter,
                )
                if runs_left is not None and runs_left <= 0:
                    return
            else:
                _log(log, "推荐页未找到职位链接。")

        if apply_seek_search(driver, config):
            _log(log, "已应用搜索条件，等待结果加载...")
            time.sleep(6)  # 地址/搜索后页面加载较慢，多等一会
        else:
            _log(log, "未自动填入搜索条件，请手动确认结果页。")

        if include_new_to_you:
            time.sleep(2)  # 等待结果页 New to you tab 加载
            if _click_new_to_you_filter(driver):
                _log(log, "已切换到 New to you，开始处理...")
                new_to_you_url = driver.current_url
                new_links = collect_job_links(driver, limit=None)
                if new_links:
                    runs_left = _process_job_links(
                        driver,
                        config,
                        job_ids,
                        new_links,
                        log,
                        runs_left,
                        seek_handle,
                        new_to_you_url,
                        total_runs=config.max_runs,
                        review_single_cover_letter=review_single_cover_letter,
                    )
                    if runs_left is not None and runs_left <= 0:
                        return
                if _click_all_jobs_filter(driver):
                    _log(log, "已切换回全部职位。")
                else:
                    _log(log, "无法切换回全部职位，继续当前页。")
            else:
                _log(log, "未找到 New to you 筛选，跳过。")

        results_url = driver.current_url

        while runs_left is None or runs_left > 0:
            if not _switch_to_handle(driver, seek_handle):
                seek_handle, _ = ensure_seek_and_chatgpt_tabs(driver, config)
                _switch_to_handle(driver, seek_handle)
            links = collect_job_links(driver, limit=None)
            if not links:
                _log(log, "未找到职位链接，再等待 5 秒重试...")
                time.sleep(5)
                links = collect_job_links(driver, limit=None)
            if not links:
                _log(log, "仍未找到职位链接，请检查 Seek 页。")
                break

            # 用当前页 URL 作为返回地址，避免翻页后回到第 1 页
            return_url = driver.current_url
            runs_left = _process_job_links(
                driver,
                config,
                job_ids,
                links,
                log,
                runs_left,
                seek_handle,
                return_url,
                total_runs=config.max_runs,
                review_single_cover_letter=review_single_cover_letter,
            )

            if runs_left is not None and runs_left <= 0:
                break
            if not go_to_next_page(driver):
                _log(log, "已到结果末页，停止。")
                break
    finally:
        driver.quit()
