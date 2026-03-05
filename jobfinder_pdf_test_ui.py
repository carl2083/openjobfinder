import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from jobfinder_core import Config
from jobfinder_web import render_text_pdf


DEFAULT_TEMPLATE = "templates/navy-gold-template.html"
DEFAULT_OUTPUT_DIR = "pdf_output_test"


class PdfTestUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF 生成测试")

        self.template_path = tk.StringVar(value=DEFAULT_TEMPLATE)
        self.output_dir = tk.StringVar(value=DEFAULT_OUTPUT_DIR)
        self.job_id = tk.StringVar(value="test_job")

        self._build_ui()

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=10, pady=10)
        frame.pack(fill=tk.BOTH, expand=True)

        self._add_labeled_entry(frame, "HTML 模板路径", self.template_path, 0)
        self._add_labeled_entry(frame, "输出目录", self.output_dir, 1)
        self._add_labeled_entry(frame, "Job ID (用于文件夹名)", self.job_id, 2)

        tk.Label(frame, text="粘贴 ChatGPT JSON：").grid(
            row=3, column=0, sticky="w", pady=(8, 2)
        )
        self.json_text = tk.Text(frame, height=18, width=80)
        self.json_text.grid(row=4, column=0, columnspan=3, sticky="nsew")

        btn_frame = tk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=3, pady=8, sticky="w")
        tk.Button(btn_frame, text="生成 PDF", command=self.start).pack(
            side=tk.LEFT, padx=4
        )

        self.log = tk.Text(frame, height=6)
        self.log.grid(row=6, column=0, columnspan=3, sticky="nsew", pady=(8, 0))

        frame.grid_rowconfigure(4, weight=1)
        frame.grid_rowconfigure(6, weight=1)
        frame.grid_columnconfigure(1, weight=1)

    def _add_labeled_entry(
        self, parent: tk.Frame, label: str, var: tk.StringVar, row: int
    ) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = tk.Entry(parent, textvariable=var, width=60)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        if "路径" in label or "目录" in label:
            tk.Button(
                parent,
                text="选择",
                command=lambda: self._select_path(var, label),
            ).grid(row=row, column=2, padx=4)

    def _select_path(self, var: tk.StringVar, label: str) -> None:
        if "目录" in label:
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def log_message(self, message: str) -> None:
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)

    def start(self) -> None:
        threading.Thread(target=self.generate_pdfs, daemon=True).start()

    def generate_pdfs(self) -> None:
        try:
            payload = json.loads(self.json_text.get("1.0", tk.END).strip())
        except Exception as exc:
            messagebox.showerror("PDF 测试", f"JSON 解析失败: {exc}")
            return

        job_id = self.job_id.get().strip() or "test_job"
        output_dir = Path(self.output_dir.get().strip() or DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        job_dir = output_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        other = payload.get("other", {})
        resume_sections = other.get("resume_sections") or {}
        cover_text = other.get("cover_letter") or other.get("Cover Letter") or ""

        config = Config(
            pdf_template_path=self.template_path.get().strip() or DEFAULT_TEMPLATE,
            pdf_output_dir=str(output_dir),
        )

        driver = self._create_driver()
        try:
            if resume_sections:
                resume_pdf = job_dir / "resume.pdf"
                render_text_pdf(
                    driver, config, "Resume", "", str(resume_pdf), resume_sections
                )
                self.log_message(f"已生成: {resume_pdf}")
            else:
                self.log_message("未找到 resume_sections，跳过简历。")

            if cover_text:
                cover_pdf = job_dir / "cover_letter.pdf"
                render_text_pdf(
                    driver, config, "Cover Letter", cover_text, str(cover_pdf), resume_sections
                )
                self.log_message(f"已生成: {cover_pdf}")
            else:
                self.log_message("未找到 cover_letter，跳过求职信。")
        except Exception as exc:
            self.log_message(f"生成失败: {exc}")
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def _create_driver(self) -> webdriver.Chrome:
        options = ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(60)
        driver.set_script_timeout(60)
        return driver


def main() -> None:
    root = tk.Tk()
    root.geometry("900x700")
    PdfTestUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
