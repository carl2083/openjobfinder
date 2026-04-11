import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional

from jobfinder_core import (
    COVER_LETTER_STYLE_OPTIONS,
    Config,
    RESUME_STYLE_OPTIONS,
    ensure_prompt_template_file,
    ensure_skill_profile_file,
    load_config,
    save_config,
)
from jobfinder_web import clear_chatgpt_draft_via_debugger, run_web_flow


CONFIG_PATH = "config.json"
SURFACE_BG = "#f3f4f7"
CARD_BG = "#ffffff"
SIDEBAR_BG = "#e9ecf2"
TEXT_PRIMARY = "#111827"
TEXT_MUTED = "#667085"
BORDER = "#d7dce5"
ACCENT = "#0f172a"
ACCENT_SOFT = "#dbe7ff"
ACCENT_TEXT = "#163152"
MACOS_SAFE_MODE_VERSION = "macOS Safe Mode v5"


def _font_family(kind: str = "body") -> str:
    if sys.platform == "darwin":
        return "Helvetica" if kind == "display" else "Arial"
    if sys.platform == "win32":
        return "Segoe UI"
    return "Arial"


class JobFinderUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.simple_mode = sys.platform == "darwin"
        self.root.title(
            f"JobFinder ({MACOS_SAFE_MODE_VERSION})" if self.simple_mode else "JobFinder"
        )
        self.root.configure(bg=SURFACE_BG)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = load_config(CONFIG_PATH)
        self.chrome_processes = []
        self.section_frames: Dict[str, tk.Frame] = {}
        self.section_buttons: Dict[str, tk.Button] = {}
        self.current_section = "basic"
        self.status_var = tk.StringVar(value="Idle")
        self.summary_var = tk.StringVar(value="Ready to launch a fresh session.")
        self.run_action_var = tk.StringVar(value="启动 Debug Chrome 并准备运行")

        self.output_excel = tk.StringVar(value=self.config.output_excel)
        self.job_location = tk.StringVar(value=self.config.job_location)
        self.keyword = tk.StringVar(value=self.config.keyword or "")
        raw_runs = (
            self.config.single_job_url
            if self.config.single_job_url
            else str(self.config.max_runs if self.config.max_runs is not None else 20)
        )
        self.max_runs = tk.StringVar(value=raw_runs)
        self.chrome_port = tk.StringVar(value=str(self.config.chrome_debug_port))
        self.chrome_user_data_dir = tk.StringVar(value=self.config.chrome_user_data_dir)
        self.chrome_path = tk.StringVar(value=self.config.chrome_path)
        self.seek_url = tk.StringVar(value=self.config.seek_url)
        self.chatgpt_url = tk.StringVar(value=self.config.chatgpt_url)
        self.chatgpt_chat_title = tk.StringVar(
            value=self.config.chatgpt_chat_title or ""
        )
        self.enable_local_sync = tk.BooleanVar(value=self.config.enable_local_sync)
        self.local_sync_path = tk.StringVar(value=self.config.local_sync_path)
        self.local_sync_pull_before_run = tk.BooleanVar(
            value=self.config.local_sync_pull_before_run
        )
        self.enable_pdf_export = tk.BooleanVar(value=self.config.enable_pdf_export)
        self.include_recommendations = tk.BooleanVar(
            value=getattr(self.config, "include_recommendations", False)
        )
        self.include_new_to_you = tk.BooleanVar(
            value=getattr(self.config, "include_new_to_you", False)
        )
        self.exit_when_done = tk.BooleanVar(
            value=getattr(self.config, "exit_when_done", False)
        )
        self.user_address = tk.StringVar(value=self.config.user_address)
        self.user_phone = tk.StringVar(value=self.config.user_phone)
        self.user_email = tk.StringVar(value=self.config.user_email)
        self.user_name = tk.StringVar(value=self.config.user_name)
        self.resume_style = tk.StringVar(
            value=getattr(self.config, "resume_style", RESUME_STYLE_OPTIONS[0])
        )
        self.cover_letter_style = tk.StringVar(
            value=getattr(
                self.config, "cover_letter_style", COVER_LETTER_STYLE_OPTIONS[0]
            )
        )
        self.skip_title_contains = tk.StringVar(
            value=getattr(self.config, "skip_title_contains", "") or ""
        )
        self.delay_min = tk.StringVar(
            value=str(getattr(self.config, "delay_between_jobs_min_sec", 10))
        )
        self.delay_max = tk.StringVar(
            value=str(getattr(self.config, "delay_between_jobs_max_sec", 20))
        )

        self._configure_styles()
        self._build_ui()

    def _configure_styles(self) -> None:
        style = ttk.Style()
        if sys.platform != "darwin":
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
            style.configure(
                "JobFinder.TEntry",
                fieldbackground=CARD_BG,
                background=CARD_BG,
                foreground=TEXT_PRIMARY,
                bordercolor=BORDER,
                lightcolor=BORDER,
                darkcolor=BORDER,
                padding=(12, 10),
                relief="flat",
            )
            style.map(
                "JobFinder.TEntry",
                bordercolor=[("focus", "#9ab6f5")],
                lightcolor=[("focus", "#9ab6f5")],
                darkcolor=[("focus", "#9ab6f5")],
            )

    def _build_ui(self) -> None:
        if self.simple_mode:
            self._build_macos_safe_v5_ui()
            return
        self._build_full_ui()

    def _build_macos_safe_v5_ui(self) -> None:
        self.root.configure(bg="#ececec")
        self.root.geometry("980x900")
        self.root.minsize(860, 780)

        container = tk.Frame(self.root, bg="#ececec", padx=12, pady=12)
        container.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(container, bg="#ececec")
        header.pack(fill=tk.X, pady=(0, 10))
        tk.Label(
            header,
            text=f"JobFinder ({MACOS_SAFE_MODE_VERSION})",
            bg="#ececec",
            fg="#111111",
            font=(_font_family("display"), 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Dedicated macOS UI rebuild. Plain Tk widgets only.",
            bg="#ececec",
            fg="#222222",
            font=(_font_family(), 11),
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.summary_var,
            bg="#ececec",
            fg="#333333",
            font=(_font_family(), 10),
            wraplength=920,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(container, bg="#ececec")
        actions.pack(fill=tk.X, pady=(0, 10))
        tk.Button(actions, textvariable=self.run_action_var, command=self._on_run_action).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        tk.Button(actions, text="Edit skill.md", command=self.edit_skill_file).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        tk.Button(actions, text="Edit prompt", command=self.edit_prompt_file).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        tk.Button(actions, text="Save Config", command=self.save).pack(side=tk.LEFT)

        basic = tk.LabelFrame(container, text="Basic Setup", padx=10, pady=10)
        basic.pack(fill=tk.X, pady=(0, 10))
        basic.grid_columnconfigure(1, weight=1, minsize=420)
        self._macos_grid_entry_row(basic, 0, "Job Location", self.job_location)
        self._macos_grid_entry_row(basic, 1, "Keyword", self.keyword)
        self._macos_grid_entry_row(basic, 2, "Run Count / JD URL", self.max_runs)

        advanced = tk.LabelFrame(container, text="Advanced", padx=10, pady=10)
        advanced.pack(fill=tk.X, pady=(0, 10))
        advanced.grid_columnconfigure(1, weight=1, minsize=420)
        self._macos_grid_entry_row(advanced, 0, "Chrome Debug Port", self.chrome_port)
        self._macos_grid_entry_row(
            advanced, 1, "Chrome User Data Dir", self.chrome_user_data_dir
        )
        self._macos_grid_entry_row(advanced, 2, "Chrome Path", self.chrome_path)
        self._macos_grid_entry_row(advanced, 3, "ChatGPT URL", self.chatgpt_url)
        self._macos_grid_entry_row(
            advanced, 4, "ChatGPT Chat Title", self.chatgpt_chat_title
        )
        self._macos_grid_entry_row(advanced, 5, "Seek URL", self.seek_url)
        self._macos_grid_entry_row(advanced, 6, "Excel Output File", self.output_excel)
        self._macos_grid_entry_row(advanced, 7, "Local Sync Path", self.local_sync_path)
        self._macos_grid_entry_row(
            advanced, 8, "Skip Title Contains", self.skip_title_contains
        )
        self._macos_grid_entry_row(advanced, 9, "Delay Min Seconds", self.delay_min)
        self._macos_grid_entry_row(advanced, 10, "Delay Max Seconds", self.delay_max)
        self._macos_grid_entry_row(advanced, 11, "Resume Style", self.resume_style)
        self._macos_grid_entry_row(
            advanced, 12, "Cover Letter Style", self.cover_letter_style
        )
        flags = tk.LabelFrame(container, text="Options", padx=10, pady=10)
        flags.pack(fill=tk.X, pady=(0, 10))
        for row, (label, var) in enumerate(
            [
                ("Include Recommendations", self.include_recommendations),
                ("Include New to You", self.include_new_to_you),
                ("Exit When Done", self.exit_when_done),
                ("Enable Local Sync", self.enable_local_sync),
                ("Pull From Sync Path Before Run", self.local_sync_pull_before_run),
                ("Enable PDF Export", self.enable_pdf_export),
            ]
        ):
            tk.Checkbutton(flags, text=label, variable=var).grid(
                row=row, column=0, sticky="w", pady=2
            )

        personal = tk.LabelFrame(container, text="Personal Info", padx=10, pady=10)
        personal.pack(fill=tk.X, pady=(0, 10))
        personal.grid_columnconfigure(1, weight=1, minsize=420)
        self._macos_grid_entry_row(personal, 0, "Name", self.user_name)
        self._macos_grid_entry_row(personal, 1, "Phone", self.user_phone)
        self._macos_grid_entry_row(personal, 2, "Email", self.user_email)
        self._macos_grid_entry_row(personal, 3, "Address", self.user_address)

        notes = tk.LabelFrame(container, text="Run Notes", padx=10, pady=10)
        notes.pack(fill=tk.X, pady=(0, 10))
        for line in [
            "1. Click the main button to launch Debug Chrome.",
            "2. Log in to Seek and ChatGPT in the opened browser.",
            "3. Confirm ChatGPT can accept input.",
            "4. Return to JobFinder and click the main button again.",
        ]:
            tk.Label(notes, text=line, anchor="w", justify="left").pack(fill=tk.X)
        tk.Label(notes, textvariable=self.status_var, font=(_font_family(), 13, "bold")).pack(
            anchor="w", pady=(8, 0)
        )

        log_wrap = tk.LabelFrame(container, text="Run Log", padx=10, pady=10)
        log_wrap.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(
            log_wrap,
            height=12,
            bg="#ffffff",
            fg="#111111",
            insertbackground="#111111",
            relief="sunken",
            bd=1,
            font=("Menlo", 10),
        )
        self.log.pack(fill=tk.BOTH, expand=True)

    def _macos_grid_entry_row(
        self, parent: tk.Widget, row: int, label: str, var: tk.StringVar
    ) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        entry = tk.Entry(
            parent,
            textvariable=var,
            width=56,
            bg="#ffffff",
            fg="#111111",
            insertbackground="#111111",
            relief="sunken",
            bd=1,
            highlightthickness=1,
            highlightbackground="#888888",
            highlightcolor="#4a90e2",
            font=(_font_family(), 11),
        )
        entry.grid(row=row, column=1, sticky="ew", pady=4)

    def _build_full_ui(self) -> None:
        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

        sidebar = tk.Frame(self.root, bg=SIDEBAR_BG, width=248)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)

        content = tk.Frame(self.root, bg=SURFACE_BG, padx=18, pady=18)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(2, weight=1)
        content.grid_rowconfigure(3, weight=1)

        self._build_sidebar(sidebar)
        self._build_header(content)
        self._build_actions(content)
        self._build_sections(content)
        self._build_log_card(content)
        self.show_section("basic")

    def _build_simple_ui(self) -> None:
        self.root.configure(bg="#dcdcdc")
        self.root.geometry("900x860")
        self.root.minsize(760, 720)

        shell = tk.Frame(self.root, bg="#dcdcdc")
        shell.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(shell, bg="#dcdcdc", padx=14, pady=12)
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text=f"JobFinder ({MACOS_SAFE_MODE_VERSION})",
            bg="#dcdcdc",
            fg="#111111",
            font=(_font_family("display"), 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Plain single-column form UI. No sidebar. No style dropdowns. Focused on stable rendering.",
            bg="#dcdcdc",
            fg="#222222",
            font=(_font_family(), 11),
            justify="left",
        ).pack(anchor="w", pady=(4, 0))
        tk.Label(
            header,
            textvariable=self.summary_var,
            bg="#dcdcdc",
            fg="#333333",
            font=(_font_family(), 10),
            justify="left",
            wraplength=820,
        ).pack(anchor="w", pady=(4, 0))

        actions = tk.Frame(shell, bg="#dcdcdc", padx=14, pady=4)
        actions.pack(fill=tk.X)
        tk.Button(
            actions,
            textvariable=self.run_action_var,
            command=self._on_run_action,
            font=(_font_family(), 11, "bold"),
            padx=12,
            pady=8,
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            actions,
            text="Edit skill.md",
            command=self.edit_skill_file,
            font=(_font_family(), 10),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            actions,
            text="Edit prompt",
            command=self.edit_prompt_file,
            font=(_font_family(), 10),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            actions,
            text="Save Config",
            command=self.save,
            font=(_font_family(), 10),
        ).pack(side=tk.LEFT)

        form_wrap = tk.Frame(shell, bg="#dcdcdc", padx=14, pady=10)
        form_wrap.pack(fill=tk.BOTH, expand=True)
        self.simple_form_body = tk.Frame(
            form_wrap,
            bg="#ffffff",
            bd=1,
            relief="solid",
            padx=14,
            pady=14,
        )
        self.simple_form_body.pack(fill=tk.BOTH, expand=True)

        self._mac_section_title("Basic Setup")
        self._mac_entry_row("Job Location", self.job_location)
        self._mac_entry_row("Keyword", self.keyword)
        self._mac_entry_row("Run Count / JD URL", self.max_runs)

        self._mac_section_title("Advanced")
        self._mac_entry_row("Chrome Debug Port", self.chrome_port)
        self._mac_entry_row("Chrome User Data Dir", self.chrome_user_data_dir)
        self._mac_entry_row("Chrome Path", self.chrome_path)
        self._mac_entry_row("ChatGPT URL", self.chatgpt_url)
        self._mac_entry_row("ChatGPT Chat Title", self.chatgpt_chat_title)
        self._mac_entry_row("Seek URL", self.seek_url)
        self._mac_entry_row("Excel Output File", self.output_excel)
        self._mac_entry_row("Local Sync Path", self.local_sync_path)
        self._mac_entry_row("Skip Title Contains", self.skip_title_contains)
        self._mac_entry_row("Delay Min Seconds", self.delay_min)
        self._mac_entry_row("Delay Max Seconds", self.delay_max)
        self._mac_entry_row("Resume Style", self.resume_style)
        self._mac_entry_row("Cover Letter Style", self.cover_letter_style)
        self._mac_checkbox_row("Include Recommendations", self.include_recommendations)
        self._mac_checkbox_row("Include New to You", self.include_new_to_you)
        self._mac_checkbox_row("Exit When Done", self.exit_when_done)
        self._mac_checkbox_row("Enable Local Sync", self.enable_local_sync)
        self._mac_checkbox_row(
            "Pull From Sync Path Before Run", self.local_sync_pull_before_run
        )
        self._mac_checkbox_row("Enable PDF Export", self.enable_pdf_export)

        self._mac_section_title("Personal Info")
        self._mac_entry_row("Name", self.user_name)
        self._mac_entry_row("Phone", self.user_phone)
        self._mac_entry_row("Email", self.user_email)
        self._mac_entry_row("Address", self.user_address)

        self._mac_section_title("Run Notes")
        for line in [
            "1. Click the main button to launch Debug Chrome.",
            "2. Log in to Seek and ChatGPT in the opened browser.",
            "3. Confirm ChatGPT can accept input.",
            "4. Return to JobFinder and click the main button again.",
        ]:
            tk.Label(
                self.simple_form_body,
                text=line,
                bg="#f4f4f4",
                fg="#333333",
                font=(_font_family(), 10),
                anchor="w",
                justify="left",
            ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            self.simple_form_body,
            textvariable=self.status_var,
            bg="#ffffff",
            fg="#111111",
            font=(_font_family(), 14, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(8, 10))

        log_wrap = tk.Frame(shell, bg="#dcdcdc", padx=14, pady=12)
        log_wrap.pack(fill=tk.BOTH, expand=False)
        tk.Label(
            log_wrap,
            text="Run Log",
            bg="#dcdcdc",
            fg="#111111",
            font=(_font_family(), 12, "bold"),
        ).pack(anchor="w")
        self.log = tk.Text(
            log_wrap,
            height=12,
            relief="sunken",
            bd=1,
            bg="#ffffff",
            fg="#111111",
            insertbackground="#111111",
            font=("Menlo", 10),
            padx=8,
            pady=8,
        )
        self.log.pack(fill=tk.BOTH, expand=True, pady=(6, 0))

    def _mac_section_title(self, text: str) -> None:
        tk.Label(
            self.simple_form_body,
            text=text,
            bg="#ffffff",
            fg="#111111",
            font=(_font_family(), 13, "bold"),
            anchor="w",
        ).pack(fill=tk.X, pady=(10, 6))

    def _mac_entry_row(self, label: str, var: tk.StringVar) -> None:
        tk.Label(
            self.simple_form_body,
            text=label,
            bg="#ffffff",
            fg="#222222",
            font=(_font_family(), 10),
            anchor="w",
        ).pack(fill=tk.X)
        entry = tk.Entry(
            self.simple_form_body,
            textvariable=var,
            font=(_font_family(), 11),
            relief="sunken",
            bd=1,
            bg="#ffffff",
            fg="#111111",
            insertbackground="#111111",
        )
        entry.pack(fill=tk.X, pady=(2, 8), ipady=6)

    def _mac_checkbox_row(self, label: str, var: tk.BooleanVar) -> None:
        tk.Checkbutton(
            self.simple_form_body,
            text=label,
            variable=var,
            bg="#ffffff",
            fg="#111111",
            activebackground="#ffffff",
            activeforeground="#111111",
            selectcolor="#ffffff",
            font=(_font_family(), 10),
            anchor="w",
        ).pack(fill=tk.X, pady=(0, 4))

    def _build_sidebar(self, parent: tk.Frame) -> None:
        top = tk.Frame(parent, bg=SIDEBAR_BG, padx=18, pady=20)
        top.pack(fill=tk.X)

        tk.Label(
            top,
            text="JobFinder",
            bg=SIDEBAR_BG,
            fg=TEXT_PRIMARY,
            font=(_font_family("display"), 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            top,
            text="Apple-style control panel for Seek + ChatGPT automation",
            bg=SIDEBAR_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 10),
            wraplength=190,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        nav = tk.Frame(parent, bg=SIDEBAR_BG, padx=14, pady=8)
        nav.pack(fill=tk.BOTH, expand=True)

        items = [
            ("basic", "Basic Setup", "搜索、次数与推荐选项"),
            ("advanced", "Advanced", "Chrome、ChatGPT 与同步"),
            ("personal", "Personal Info", "简历 Header 信息"),
            ("runlog", "Run Log", "运行提示与当前状态"),
        ]
        for key, title, subtitle in items:
            button = tk.Button(
                nav,
                text=title,
                command=lambda value=key: self.show_section(value),
                anchor="w",
                relief="flat",
                bd=0,
                padx=16,
                pady=14,
                bg=SIDEBAR_BG,
                fg=TEXT_PRIMARY,
                activebackground=ACCENT_SOFT,
                activeforeground=TEXT_PRIMARY,
                font=(_font_family(), 11, "bold"),
                cursor="hand2",
            )
            button.pack(fill=tk.X, pady=(0, 8))
            self.section_buttons[key] = button

            label = tk.Label(
                nav,
                text=subtitle,
                bg=SIDEBAR_BG,
                fg=TEXT_MUTED,
                font=(_font_family(), 9),
                justify="left",
                anchor="w",
                padx=18,
            )
            label.pack(fill=tk.X, pady=(0, 12))

        footer = tk.Frame(parent, bg=SIDEBAR_BG, padx=18, pady=18)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        tk.Label(
            footer,
            text="Tip",
            bg=SIDEBAR_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            footer,
            text="留空 ChatGPT 对话名称时，会优先使用当前对话，通常更快。",
            bg=SIDEBAR_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 9),
            justify="left",
            wraplength=190,
        ).pack(anchor="w", pady=(6, 0))

    def _build_header(self, parent: tk.Frame) -> None:
        card = self._create_card(parent)
        card.grid(row=0, column=0, sticky="ew", pady=(0, 14))
        card.grid_columnconfigure(0, weight=1)
        card.grid_columnconfigure(1, weight=0)

        text_block = tk.Frame(card, bg=CARD_BG)
        text_block.grid(row=0, column=0, sticky="w")

        tk.Label(
            text_block,
            text="Ready to apply smarter",
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=(_font_family("display"), 24, "bold"),
        ).pack(anchor="w")
        tk.Label(
            text_block,
            text="A calmer desktop layout with larger controls, grouped settings, and a cleaner run workflow.",
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 11),
            wraplength=620,
            justify="left",
        ).pack(anchor="w", pady=(8, 0))

        status_card = tk.Frame(
            card,
            bg="#f7f8fb",
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=18,
            pady=16,
        )
        status_card.grid(row=0, column=1, sticky="e", padx=(16, 0))
        tk.Label(
            status_card,
            text="Status",
            bg="#f7f8fb",
            fg=TEXT_MUTED,
            font=(_font_family(), 9, "bold"),
        ).pack(anchor="w")
        tk.Label(
            status_card,
            textvariable=self.status_var,
            bg="#f7f8fb",
            fg=TEXT_PRIMARY,
            font=(_font_family(), 16, "bold"),
        ).pack(anchor="w", pady=(6, 0))
        tk.Label(
            status_card,
            textvariable=self.summary_var,
            bg="#f7f8fb",
            fg=TEXT_MUTED,
            font=(_font_family(), 9),
            wraplength=220,
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _build_actions(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=SURFACE_BG)
        if self.simple_mode:
            bar.pack(fill=tk.X, pady=(0, 14))
        else:
            bar.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        for col in range(5):
            bar.grid_columnconfigure(col, weight=1)

        self.btn_run_action = self._make_action_button(
            bar,
            command=self._on_run_action,
            textvariable=self.run_action_var,
            bg=ACCENT,
            fg="#ffffff",
        )
        self.btn_run_action.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 10))

        self.btn_edit_skill = self._make_action_button(
            bar,
            command=self.edit_skill_file,
            text="编辑 skill.md",
            bg="#eef2f7",
            fg=TEXT_PRIMARY,
        )
        self.btn_edit_skill.grid(row=0, column=2, sticky="ew", padx=5)

        self.btn_edit_prompt = self._make_action_button(
            bar,
            command=self.edit_prompt_file,
            text="编辑 prompt",
            bg="#eef2f7",
            fg=TEXT_PRIMARY,
        )
        self.btn_edit_prompt.grid(row=0, column=3, sticky="ew", padx=5)

        self.btn_save = self._make_action_button(
            bar,
            command=self.save,
            text="保存配置",
            bg=ACCENT_SOFT,
            fg=ACCENT_TEXT,
        )
        self.btn_save.grid(row=0, column=4, sticky="ew", padx=(10, 0))

    def _build_sections(self, parent: tk.Frame) -> None:
        holder = tk.Frame(parent, bg=SURFACE_BG)
        holder.grid(row=2, column=0, sticky="nsew", pady=(0, 14))
        holder.grid_columnconfigure(0, weight=1)
        holder.grid_rowconfigure(0, weight=1)
        self.section_holder = holder

        basic = tk.Frame(holder, bg=SURFACE_BG)
        advanced = tk.Frame(holder, bg=SURFACE_BG)
        personal = tk.Frame(holder, bg=SURFACE_BG)
        runlog = tk.Frame(holder, bg=SURFACE_BG)
        for frame in (basic, advanced, personal, runlog):
            frame.grid(row=0, column=0, sticky="nsew")

        self.section_frames = {
            "basic": basic,
            "advanced": advanced,
            "personal": personal,
            "runlog": runlog,
        }

        self._build_basic_section(basic)
        self._build_advanced_section(advanced)
        self._build_personal_section(personal)
        self._build_runlog_section(runlog)

    def _build_basic_section(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        search_card = self._create_titled_card(
            parent,
            "Search Setup",
            "核心搜索条件和运行目标，适合每次启动前先确认。",
        )
        if self.simple_mode:
            search_card.pack(fill=tk.X, pady=(0, 12))
        else:
            search_card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            search_card.grid_columnconfigure(0, weight=1)
        self._add_text_field(search_card, "职位地点", self.job_location, 0)
        self._add_text_field(search_card, "关键词", self.keyword, 1)
        self._add_text_field(search_card, "运行次数 / JD URL", self.max_runs, 2)

    def _build_advanced_section(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        if not self.simple_mode:
            parent.grid_columnconfigure(1, weight=1)

        style_card = self._create_titled_card(
            parent,
            "Writing Style & Run Behavior",
            "控制 resume / cover letter 的写作风格，以及处理顺序和运行结束行为。",
        )
        if self.simple_mode:
            style_card.pack(fill=tk.X, pady=(0, 12))
        else:
            style_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
            style_card.grid_columnconfigure(0, weight=1)
        self._add_dropdown_field(
            style_card, "Resume Style", self.resume_style, RESUME_STYLE_OPTIONS
        )
        self._add_dropdown_field(
            style_card,
            "Cover Letter Style",
            self.cover_letter_style,
            COVER_LETTER_STYLE_OPTIONS,
        )
        self._add_checkbox_field(style_card, "优先处理推荐页", self.include_recommendations, 0)
        self._add_checkbox_field(style_card, "优先处理 New to you", self.include_new_to_you, 1)
        self._add_checkbox_field(style_card, "完成之后退出程序", self.exit_when_done, 2)

        chrome_card = self._create_titled_card(
            parent,
            "Chrome & ChatGPT",
            "调试端口、Profile 与 ChatGPT 会话设置。",
        )
        if self.simple_mode:
            chrome_card.pack(fill=tk.X, pady=(0, 12))
        else:
            chrome_card.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
            chrome_card.grid_columnconfigure(0, weight=1)
        self._add_text_field(chrome_card, "Chrome Debug 端口", self.chrome_port, 0)
        self._add_text_field(
            chrome_card,
            "Chrome 用户目录",
            self.chrome_user_data_dir,
            1,
            browse="dir",
        )
        self._add_text_field(
            chrome_card, "Chrome 路径", self.chrome_path, 2, browse="file"
        )
        self._add_text_field(chrome_card, "ChatGPT URL", self.chatgpt_url, 3)
        self._add_text_field(
            chrome_card,
            "ChatGPT 对话名称 (留空=当前对话)",
            self.chatgpt_chat_title,
            4,
        )
        self._add_text_field(chrome_card, "搜索地址 (Seek URL)", self.seek_url, 5)

        file_card = self._create_titled_card(
            parent,
            "Files & Timing",
            "Excel 输出、同步和节流相关设置。",
        )
        if self.simple_mode:
            file_card.pack(fill=tk.X, pady=(0, 12))
        else:
            file_card.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=(8, 0), pady=(0, 12))
            file_card.grid_columnconfigure(0, weight=1)
        self._add_text_field(
            file_card, "Excel 输出文件", self.output_excel, 0, browse="savefile"
        )
        self._add_checkbox_field(file_card, "本地盘符同步(不上传)", self.enable_local_sync, 1)
        self._add_text_field(
            file_card, "同步文件路径", self.local_sync_path, 2, browse="savefile"
        )
        self._add_checkbox_field(
            file_card, "运行前从同步路径读取", self.local_sync_pull_before_run, 3
        )
        self._add_checkbox_field(file_card, "导出简历/求职信 PDF", self.enable_pdf_export, 4)
        self._add_text_field(
            file_card,
            "跳过标题包含 (英文或中文逗号分隔)",
            self.skip_title_contains,
            5,
        )
        self._add_text_field(file_card, "任务间隔秒数 (最小)", self.delay_min, 6)
        self._add_text_field(file_card, "任务间隔秒数 (最大)", self.delay_max, 7)

    def _build_personal_section(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)

        card = self._create_titled_card(
            parent,
            "Resume Header Profile",
            "这些信息会用于 PDF Header 和部分简历生成场景。",
        )
        if self.simple_mode:
            card.pack(fill=tk.X, pady=(0, 12))
        else:
            card.grid(row=0, column=0, sticky="nsew", pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)
        self._add_text_field(card, "姓名 (Header)", self.user_name, 0)
        self._add_text_field(card, "电话 (Header)", self.user_phone, 1)
        self._add_text_field(card, "Email (Header)", self.user_email, 2)
        self._add_text_field(card, "地址 (Header)", self.user_address, 3)

    def _build_runlog_section(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        if not self.simple_mode:
            parent.grid_columnconfigure(1, weight=1)

        card = self._create_titled_card(
            parent,
            "Run Checklist",
            "每次运行前快速核对，能减少因浏览器状态残留导致的中断。",
        )
        if self.simple_mode:
            card.pack(fill=tk.X, pady=(0, 12))
        else:
            card.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 12))
        for line in [
            "1. 先保存配置，再启动 Debug Chrome。",
            "2. 确认 ChatGPT 已登录，并且草稿输入框已被清空。",
            "3. 如需新会话更快，保持 ChatGPT 对话名称为空。",
            "4. 日志区会持续显示当前处理进度与异常。",
        ]:
            tk.Label(
                card,
                text=line,
                bg=CARD_BG,
                fg=TEXT_PRIMARY,
                font=(_font_family(), 10),
                justify="left",
                anchor="w",
                wraplength=420,
            ).pack(anchor="w", pady=(0, 8))

        stats = self._create_titled_card(
            parent,
            "Session Summary",
            "当前窗口内的快速状态摘要。",
        )
        if self.simple_mode:
            stats.pack(fill=tk.X, pady=(0, 12))
        else:
            stats.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=(0, 12))
        tk.Label(
            stats,
            textvariable=self.status_var,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=(_font_family(), 20, "bold"),
        ).pack(anchor="w")
        tk.Label(
            stats,
            textvariable=self.summary_var,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 10),
            wraplength=380,
            justify="left",
        ).pack(anchor="w", pady=(10, 0))

    def _build_log_card(self, parent: tk.Frame) -> None:
        card = self._create_titled_card(
            parent,
            "Run Log",
            "实时输出会显示在这里，便于观察 Chrome、Seek 和 ChatGPT 的当前状态。",
        )
        if self.simple_mode:
            card.pack(fill=tk.BOTH, expand=True)
        else:
            card.grid(row=3, column=0, sticky="nsew")

        self.log = tk.Text(
            card,
            height=12,
            bg="#fbfcfe",
            fg=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            insertbackground=TEXT_PRIMARY,
            font=("Consolas", 10),
            padx=14,
            pady=14,
        )
        self.log.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    def _create_card(self, parent: tk.Widget) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=CARD_BG,
            padx=20,
            pady=20,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

    def _create_titled_card(
        self, parent: tk.Widget, title: str, subtitle: str
    ) -> tk.Frame:
        card = self._create_card(parent)
        tk.Label(
            card,
            text=title,
            bg=CARD_BG,
            fg=TEXT_PRIMARY,
            font=(_font_family(), 14, "bold"),
        ).pack(anchor="w")
        tk.Label(
            card,
            text=subtitle,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 10),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", pady=(6, 16))
        return card

    def _make_action_button(
        self,
        parent: tk.Widget,
        command,
        bg: str,
        fg: str,
        text: Optional[str] = None,
        textvariable: Optional[tk.StringVar] = None,
        state: str = tk.NORMAL,
    ) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            textvariable=textvariable,
            command=command,
            relief="flat",
            bd=0,
            bg=bg,
            fg=fg,
            activebackground=bg,
            activeforeground=fg,
            font=(_font_family(), 11, "bold"),
            padx=18,
            pady=16,
            cursor="hand2",
            state=state,
        )

    def _add_text_field(
        self,
        parent: tk.Frame,
        label: str,
        var: tk.StringVar,
        row: int,
        browse: Optional[str] = None,
    ) -> None:
        field = tk.Frame(parent, bg=CARD_BG)
        field.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            field,
            text=label,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 9, "bold"),
        ).grid(row=0, column=0, sticky="w")
        field.grid_columnconfigure(0, weight=1)

        if sys.platform == "darwin":
            entry = tk.Entry(
                field,
                textvariable=var,
                relief="solid",
                bd=1,
                bg=CARD_BG,
                fg=TEXT_PRIMARY,
                insertbackground=TEXT_PRIMARY,
                font=(_font_family(), 11),
            )
        else:
            entry = ttk.Entry(field, textvariable=var, style="JobFinder.TEntry")
        entry.grid(row=1, column=0, sticky="ew", pady=(8, 0), ipady=6)
        if browse:
            tk.Button(
                field,
                text="选择",
                command=lambda mode=browse, value=var: self._select_path(value, mode),
                relief="flat",
                bd=0,
                bg="#eef2f7",
                fg=TEXT_PRIMARY,
                activebackground="#eef2f7",
                activeforeground=TEXT_PRIMARY,
                font=(_font_family(), 9, "bold"),
                padx=14,
                pady=10,
                cursor="hand2",
            ).grid(row=1, column=1, padx=(10, 0), pady=(8, 0))

    def _add_checkbox_field(
        self, parent: tk.Frame, label: str, var: tk.BooleanVar, row: int
    ) -> None:
        del row
        wrapper = tk.Frame(parent, bg="#f8f9fc", padx=14, pady=12)
        wrapper.pack(fill=tk.X, pady=(0, 12))
        cb = tk.Checkbutton(
            wrapper,
            text=label,
            variable=var,
            bg="#f8f9fc",
            fg=TEXT_PRIMARY,
            activebackground="#f8f9fc",
            activeforeground=TEXT_PRIMARY,
            selectcolor=CARD_BG,
            font=(_font_family(), 10),
            anchor="w",
        )
        cb.pack(anchor="w")

    def _add_dropdown_field(
        self,
        parent: tk.Frame,
        label: str,
        var: tk.StringVar,
        values,
    ) -> None:
        field = tk.Frame(parent, bg=CARD_BG)
        field.pack(fill=tk.X, pady=(0, 14))
        tk.Label(
            field,
            text=label,
            bg=CARD_BG,
            fg=TEXT_MUTED,
            font=(_font_family(), 9, "bold"),
        ).pack(anchor="w")
        if sys.platform == "darwin":
            combo = tk.OptionMenu(field, var, *list(values))
            combo.configure(
                bg=CARD_BG,
                fg=TEXT_PRIMARY,
                activebackground="#eef2f7",
                activeforeground=TEXT_PRIMARY,
                relief="solid",
                bd=1,
                font=(_font_family(), 10),
                anchor="w",
                highlightthickness=0,
            )
            combo["menu"].configure(font=(_font_family(), 10))
            combo.pack(fill=tk.X, pady=(8, 0))
        else:
            combo = ttk.Combobox(
                field,
                textvariable=var,
                values=list(values),
                state="readonly",
                font=(_font_family(), 10),
            )
            combo.pack(fill=tk.X, pady=(8, 0))

    def _select_path(self, var: tk.StringVar, browse: str) -> None:
        if browse == "dir":
            path = filedialog.askdirectory()
        elif browse == "savefile":
            path = filedialog.asksaveasfilename()
        else:
            path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def show_section(self, section: str) -> None:
        self.current_section = section
        for key, frame in self.section_frames.items():
            if key == section:
                frame.tkraise()
        for key, button in self.section_buttons.items():
            if key == section:
                button.configure(bg=ACCENT_SOFT, fg=ACCENT_TEXT)
            else:
                button.configure(bg=SIDEBAR_BG, fg=TEXT_PRIMARY)

    def log_message(self, message: str) -> None:
        def append() -> None:
            self.log.insert(tk.END, message + "\n")
            self.log.see(tk.END)
            self.summary_var.set(message[:120])

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self.root.after(0, append)

    def _set_status(self, value: str) -> None:
        if threading.current_thread() is threading.main_thread():
            self.status_var.set(value)
        else:
            self.root.after(0, lambda: self.status_var.set(value))

    def _read_config(self) -> Config:
        max_runs_value: Optional[int]
        raw_runs = self.max_runs.get().strip()
        single_job_url: Optional[str] = None
        if raw_runs:
            if raw_runs.lower().startswith(("http://", "https://")):
                single_job_url = raw_runs
                max_runs_value = None
            else:
                max_runs_value = int(raw_runs)
        else:
            max_runs_value = None

        return Config(
            output_excel=self.output_excel.get().strip() or "job_results.xlsx",
            job_location=self.job_location.get().strip(),
            keyword=self.keyword.get().strip() or None,
            max_runs=max_runs_value,
            single_job_url=single_job_url,
            include_recommendations=bool(self.include_recommendations.get()),
            include_new_to_you=bool(self.include_new_to_you.get()),
            exit_when_done=bool(self.exit_when_done.get()),
            chrome_debug_port=int(self.chrome_port.get().strip() or 9222),
            chrome_user_data_dir=self.chrome_user_data_dir.get().strip(),
            chrome_path=self.chrome_path.get().strip(),
            seek_url=self.seek_url.get().strip() or "https://www.seek.com.au/",
            chatgpt_url=self.chatgpt_url.get().strip() or "https://chat.openai.com/",
            chatgpt_chat_title=self.chatgpt_chat_title.get().strip(),
            enable_local_sync=bool(self.enable_local_sync.get()),
            local_sync_path=self.local_sync_path.get().strip(),
            local_sync_pull_before_run=bool(self.local_sync_pull_before_run.get()),
            enable_pdf_export=bool(self.enable_pdf_export.get()),
            skip_title_contains=self.skip_title_contains.get().strip(),
            delay_between_jobs_min_sec=int(self.delay_min.get().strip() or "10"),
            delay_between_jobs_max_sec=int(self.delay_max.get().strip() or "20"),
            batch_size=1,
            pdf_css_path="",
            pdf_output_dir="pdf_output",
            pdf_template_path="templates/navy-gold-template.html",
            user_address=self.user_address.get().strip(),
            user_phone=self.user_phone.get().strip(),
            user_email=self.user_email.get().strip(),
            user_name=self.user_name.get().strip() or "carl chen",
            resume_style=self.resume_style.get().strip() or RESUME_STYLE_OPTIONS[0],
            cover_letter_style=(
                self.cover_letter_style.get().strip()
                or COVER_LETTER_STYLE_OPTIONS[0]
            ),
        )

    def save(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        self._set_status("Saved")
        self.summary_var.set("配置已保存。")
        messagebox.showinfo("JobFinder", "配置已保存。")

    def _on_run_action(self) -> None:
        if self.run_action_var.get() == "继续运行":
            self.start_run()
            return
        if self.launch_chrome():
            self.run_action_var.set("继续运行")

    def launch_chrome(self) -> bool:
        config = self._read_config()
        save_config(CONFIG_PATH, config)
        chrome_path = config.chrome_path.strip()
        if not chrome_path:
            chrome_path = self._detect_chrome_path()
            if chrome_path:
                self.chrome_path.set(chrome_path)
            else:
                messagebox.showerror("JobFinder", "请填写 Chrome 路径。")
                return False

        user_dir = config.chrome_user_data_dir.strip()
        if not user_dir:
            user_dir = str(Path.cwd() / "chrome-profile")

        cmd = [
            chrome_path,
            f"--remote-debugging-port={config.chrome_debug_port}",
            f"--user-data-dir={user_dir}",
            "--new-window",
            config.seek_url or "https://www.seek.com.au/",
        ]
        creationflags = (
            getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            if sys.platform == "win32"
            else 0
        )
        try:
            proc = subprocess.Popen(cmd, creationflags=creationflags)
            self.chrome_processes.append(proc)
            self.log_message("已启动 Chrome Debug。")
        except PermissionError:
            if sys.platform == "win32":
                start_cmd = ["cmd", "/c", "start", "/b", "", chrome_path] + cmd[1:]
                subprocess.Popen(start_cmd, creationflags=creationflags)
                self.log_message("已通过 start 启动 Chrome Debug。")
            else:
                raise
        except FileNotFoundError:
            messagebox.showerror("JobFinder", "找不到 Chrome 可执行文件。")
            return False

        self._set_status("Launching")
        self.summary_var.set("正在打开 Seek 和 ChatGPT 标签页。")

        def open_chatgpt_tab() -> None:
            time.sleep(1)
            try:
                proc = subprocess.Popen(
                    [
                        chrome_path,
                        f"--remote-debugging-port={config.chrome_debug_port}",
                        f"--user-data-dir={user_dir}",
                        "--new-tab",
                        config.chatgpt_url or "https://chat.openai.com/",
                    ],
                    creationflags=creationflags,
                )
                self.chrome_processes.append(proc)
                self.log_message("已尝试打开 ChatGPT 标签页。")
            except Exception as exc:
                self.log_message(f"打开 ChatGPT 标签页失败: {exc}")
                return

            time.sleep(4)
            cleared = clear_chatgpt_draft_via_debugger(config, log=self.log_message)
            if cleared:
                self._set_status("Ready")
                self.summary_var.set("请先登录 Seek 和 ChatGPT，确认页面可用后点击“继续运行”。")
            else:
                self._set_status("Ready")
                self.summary_var.set("请先登录 Seek 和 ChatGPT，再点击“继续运行”。")

        threading.Thread(target=open_chatgpt_tab, daemon=True).start()
        self.log_message("已尝试打开 Seek 和 ChatGPT 标签页。请先完成登录，再点击“继续运行”。")
        return True

    def start_run(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        exit_when_done = bool(self.config.exit_when_done)
        self._set_status("Running")
        self.summary_var.set("自动处理流程已启动。")
        self.btn_run_action.config(state=tk.DISABLED)

        def worker() -> None:
            try:
                run_web_flow(
                    self.config,
                    log=self.log_message,
                    include_landing_recommendations=self.config.include_recommendations,
                    include_new_to_you=self.config.include_new_to_you,
                )
                self.log_message("完成。")
                self._set_status("Completed")
                self.root.after(0, lambda: self.btn_run_action.config(state=tk.NORMAL))
                self.run_action_var.set("再次启动新一轮")
                if exit_when_done:
                    self.root.after(0, self.on_close)
            except Exception as exc:  # pragma: no cover - UI error display
                self.log_message(f"错误: {exc}")
                self._set_status("Error")
                self.root.after(0, lambda: self.btn_run_action.config(state=tk.NORMAL))
                self.run_action_var.set("继续运行")

        threading.Thread(target=worker, daemon=True).start()

    def _detect_chrome_path(self) -> Optional[str]:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return None

    def edit_skill_file(self) -> None:
        path = Path(ensure_skill_profile_file(str(Path.cwd() / "skill.md")))
        try:
            self._open_path(path)
        except Exception:
            messagebox.showerror("JobFinder", "无法打开 skill.md。")

    def edit_prompt_file(self) -> None:
        path = Path(ensure_prompt_template_file(str(Path.cwd() / "prompt.md")))
        try:
            self._open_path(path)
        except Exception:
            messagebox.showerror("JobFinder", "无法打开 prompt.md。")

    def _open_path(self, path: Path) -> None:
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
            return
        subprocess.Popen(["xdg-open", str(path)])

    def on_close(self) -> None:
        self._close_chrome_processes()
        self.root.destroy()

    def _close_chrome_processes(self) -> None:
        for proc in list(self.chrome_processes):
            if proc and proc.poll() is None:
                try:
                    if sys.platform == "win32":
                        creationflags = getattr(
                            subprocess, "CREATE_NO_WINDOW", 0x08000000
                        )
                        subprocess.run(
                            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            capture_output=True,
                            creationflags=creationflags,
                        )
                    else:
                        proc.terminate()
                except Exception:
                    pass


def main() -> None:
    root = tk.Tk()
    root.geometry("1280x860")
    root.minsize(1120, 760)
    JobFinderUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
