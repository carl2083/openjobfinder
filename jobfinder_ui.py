import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

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


class UiSignals(QObject):
    log = Signal(str)
    status = Signal(str)
    summary = Signal(str)
    run_button_text = Signal(str)
    run_button_enabled = Signal(bool)
    chrome_ready = Signal(bool)


class JobFinderWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JobFinder")
        self.resize(1120, 860)
        self.setMinimumSize(920, 720)

        self.config = load_config(CONFIG_PATH)
        self.chrome_processes = []
        self.signals = UiSignals()
        self.chrome_ready = False

        self._build_ui()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self.status_value.setText)
        self.signals.summary.connect(self.summary_value.setText)
        self.signals.run_button_text.connect(self.run_action_button.setText)
        self.signals.run_button_enabled.connect(self.run_action_button.setEnabled)
        self.signals.chrome_ready.connect(self._set_chrome_ready)
        self._load_config_into_form()
        self.signals.status.emit("Idle")
        self.signals.summary.emit("Ready to launch a fresh session.")

    def _build_ui(self) -> None:
        self._apply_styles()

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        root.addWidget(self._build_header())
        root.addLayout(self._build_actions())
        root.addWidget(self._build_tabs(), 1)
        root.addWidget(self._build_log_panel(), 1)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f5f7;
                color: #111827;
                font-size: 13px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d7dce5;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 12px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 4px;
            }
            QLineEdit, QComboBox, QTextEdit {
                background: #ffffff;
                border: 1px solid #c7ced9;
                border-radius: 8px;
                padding: 8px 10px;
                color: #111827;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #4a90e2;
            }
            QPushButton {
                background: #e8edf5;
                border: 1px solid #c7ced9;
                border-radius: 9px;
                padding: 10px 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #dde5f1;
            }
            QPushButton#primaryButton {
                background: #111827;
                color: white;
                border: 1px solid #111827;
            }
            QPushButton#primaryButton:hover {
                background: #1f2937;
            }
            QTabWidget::pane {
                border: 1px solid #d7dce5;
                background: #ffffff;
                border-radius: 10px;
                top: -1px;
            }
            QTabBar::tab {
                background: #e9edf4;
                border: 1px solid #d7dce5;
                padding: 10px 14px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom-color: #ffffff;
            }
            """
        )

    def _build_header(self) -> QWidget:
        frame = QFrame()
        layout = QGridLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("JobFinder")
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel(
            "Cross-platform desktop UI rebuilt with Qt. Fill the form, launch Debug Chrome, log in, then continue."
        )
        subtitle.setWordWrap(True)

        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)
        self.status_value = QLabel("Idle")
        status_font = QFont()
        status_font.setPointSize(16)
        status_font.setBold(True)
        self.status_value.setFont(status_font)
        self.summary_value = QLabel("Ready")
        self.summary_value.setWordWrap(True)
        status_layout.addWidget(self.status_value)
        status_layout.addWidget(self.summary_value)

        layout.addWidget(title, 0, 0)
        layout.addWidget(subtitle, 1, 0)
        layout.addWidget(status_box, 0, 1, 2, 1)
        layout.setColumnStretch(0, 1)
        return frame

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.run_action_button = QPushButton("Launch Debug Chrome And Prepare Run")
        self.run_action_button.setObjectName("primaryButton")
        self.run_action_button.clicked.connect(self._on_run_action)

        self.edit_skill_button = QPushButton("Edit skill.md")
        self.edit_skill_button.clicked.connect(self.edit_skill_file)

        self.edit_prompt_button = QPushButton("Edit prompt")
        self.edit_prompt_button.clicked.connect(self.edit_prompt_file)

        self.open_output_button = QPushButton("Open Output Folder")
        self.open_output_button.clicked.connect(self.open_output_folder)

        self.save_button = QPushButton("Save Config")
        self.save_button.clicked.connect(self.save)

        layout.addWidget(self.run_action_button, 2)
        layout.addWidget(self.edit_skill_button)
        layout.addWidget(self.edit_prompt_button)
        layout.addWidget(self.open_output_button)
        layout.addWidget(self.save_button)
        return layout

    def _build_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_basic_tab(), "Basic")
        self.tabs.addTab(self._build_advanced_tab(), "Advanced")
        self.tabs.addTab(self._build_personal_tab(), "Personal")
        self.tabs.addTab(self._build_notes_tab(), "Run Notes")
        return self.tabs

    def _build_basic_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(self._group_with_form(
            "Basic Setup",
            [
                ("Job Location", self._line("job_location")),
                ("Keyword", self._line("keyword")),
                ("Run Count / JD URL", self._line("max_runs")),
            ],
        ))
        layout.addStretch(1)
        return widget

    def _build_advanced_tab(self) -> QWidget:
        widget = QWidget()
        outer = QVBoxLayout(widget)

        top = QHBoxLayout()
        top.addWidget(
            self._group_with_form(
                "Writing Style & Run Behavior",
                [
                    ("Resume Style", self._combo("resume_style", RESUME_STYLE_OPTIONS)),
                    (
                        "Cover Letter Style",
                        self._combo("cover_letter_style", COVER_LETTER_STYLE_OPTIONS),
                    ),
                ],
                checkboxes=[
                    ("Include Recommendations", self._check("include_recommendations")),
                    ("Include New To You", self._check("include_new_to_you")),
                    ("Exit When Done", self._check("exit_when_done")),
                ],
            ),
            1,
        )
        top.addWidget(
            self._group_with_form(
                "Chrome & ChatGPT",
                [
                    ("Chrome Debug Port", self._line("chrome_port")),
                    ("Chrome User Data Dir", self._path_line("chrome_user_data_dir", directory=True)),
                    ("Chrome Path", self._path_line("chrome_path", file_mode=True)),
                    ("ChatGPT URL", self._line("chatgpt_url")),
                    ("ChatGPT Chat Title", self._line("chatgpt_chat_title")),
                    ("Seek URL", self._line("seek_url")),
                ],
            ),
            1,
        )
        outer.addLayout(top)

        outer.addWidget(
            self._group_with_form(
                "Files & Timing",
                [
                    ("Excel Output File", self._path_line("output_excel", save_mode=True)),
                    ("Local Sync Path", self._path_line("local_sync_path", save_mode=True)),
                    ("Skip Title Contains", self._line("skip_title_contains")),
                    ("Delay Min Seconds", self._line("delay_min")),
                    ("Delay Max Seconds", self._line("delay_max")),
                ],
                checkboxes=[
                    ("Enable Local Sync", self._check("enable_local_sync")),
                    (
                        "Pull From Sync Path Before Run",
                        self._check("local_sync_pull_before_run"),
                    ),
                    ("Enable PDF Export", self._check("enable_pdf_export")),
                ],
            )
        )
        outer.addStretch(1)
        return widget

    def _build_personal_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(
            self._group_with_form(
                "Personal Info",
                [
                    ("Name", self._line("user_name")),
                    ("Phone", self._line("user_phone")),
                    ("Email", self._line("user_email")),
                    ("Address", self._line("user_address")),
                ],
            )
        )
        layout.addStretch(1)
        return widget

    def _build_notes_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        group = QGroupBox("Run Notes")
        g = QVBoxLayout(group)
        for line in [
            "1. Click the main button to launch Debug Chrome.",
            "2. Log in to Seek and ChatGPT in the opened browser.",
            "3. Confirm ChatGPT can accept input.",
            "4. Return to JobFinder and click the main button again.",
        ]:
            label = QLabel(line)
            label.setWordWrap(True)
            g.addWidget(label)
        layout.addWidget(group)
        layout.addStretch(1)
        return widget

    def _build_log_panel(self) -> QWidget:
        group = QGroupBox("Run Log")
        layout = QVBoxLayout(group)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(220)
        layout.addWidget(self.log_view)
        return group

    def _group_with_form(self, title: str, rows, checkboxes=None) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        for label, widget in rows:
            form.addRow(label, widget)
        layout.addLayout(form)

        if checkboxes:
            for _, checkbox in checkboxes:
                layout.addWidget(checkbox)

        return group

    def _line(self, name: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setMinimumWidth(320)
        setattr(self, name, widget)
        return widget

    def _combo(self, name: str, values) -> QComboBox:
        combo = QComboBox()
        combo.addItems(list(values))
        combo.setEditable(False)
        combo.setMinimumWidth(320)
        setattr(self, name, combo)
        return combo

    def _check(self, name: str) -> QCheckBox:
        cb = QCheckBox()
        setattr(self, name, cb)
        return cb

    def _path_line(
        self,
        name: str,
        directory: bool = False,
        file_mode: bool = False,
        save_mode: bool = False,
    ) -> QWidget:
        wrapper = QWidget()
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        edit = QLineEdit()
        edit.setMinimumWidth(320)
        setattr(self, name, edit)
        button = QPushButton("Browse")
        button.clicked.connect(
            lambda: self._select_path(edit, directory=directory, file_mode=file_mode, save_mode=save_mode)
        )
        layout.addWidget(edit, 1)
        layout.addWidget(button)
        return wrapper

    def _select_path(
        self,
        target: QLineEdit,
        directory: bool = False,
        file_mode: bool = False,
        save_mode: bool = False,
    ) -> None:
        if directory:
            path = QFileDialog.getExistingDirectory(self, "Select Directory")
        elif save_mode:
            path, _ = QFileDialog.getSaveFileName(self, "Select File")
        elif file_mode:
            path, _ = QFileDialog.getOpenFileName(self, "Select File")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File")
        if path:
            target.setText(path)

    def _load_config_into_form(self) -> None:
        cfg = self.config
        raw_runs = cfg.single_job_url if cfg.single_job_url else str(cfg.max_runs if cfg.max_runs is not None else 20)
        self.output_excel.setText(cfg.output_excel)
        self.job_location.setText(cfg.job_location)
        self.keyword.setText(cfg.keyword or "")
        self.max_runs.setText(raw_runs)
        self.chrome_port.setText(str(cfg.chrome_debug_port))
        self.chrome_user_data_dir.setText(cfg.chrome_user_data_dir)
        self.chrome_path.setText(cfg.chrome_path)
        self.seek_url.setText(cfg.seek_url)
        self.chatgpt_url.setText(cfg.chatgpt_url)
        self.chatgpt_chat_title.setText(cfg.chatgpt_chat_title or "")
        self.enable_local_sync.setChecked(cfg.enable_local_sync)
        self.local_sync_path.setText(cfg.local_sync_path)
        self.local_sync_pull_before_run.setChecked(cfg.local_sync_pull_before_run)
        self.enable_pdf_export.setChecked(cfg.enable_pdf_export)
        self.include_recommendations.setChecked(getattr(cfg, "include_recommendations", False))
        self.include_new_to_you.setChecked(getattr(cfg, "include_new_to_you", False))
        self.exit_when_done.setChecked(getattr(cfg, "exit_when_done", False))
        self.user_address.setText(cfg.user_address)
        self.user_phone.setText(cfg.user_phone)
        self.user_email.setText(cfg.user_email)
        self.user_name.setText(cfg.user_name)
        self.resume_style.setCurrentText(getattr(cfg, "resume_style", RESUME_STYLE_OPTIONS[0]))
        self.cover_letter_style.setCurrentText(
            getattr(cfg, "cover_letter_style", COVER_LETTER_STYLE_OPTIONS[0])
        )
        self.skip_title_contains.setText(getattr(cfg, "skip_title_contains", "") or "")
        self.delay_min.setText(str(getattr(cfg, "delay_between_jobs_min_sec", 10)))
        self.delay_max.setText(str(getattr(cfg, "delay_between_jobs_max_sec", 20)))

    def _read_config(self) -> Config:
        max_runs_value: Optional[int]
        raw_runs = self.max_runs.text().strip()
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
            output_excel=self.output_excel.text().strip() or "job_results.xlsx",
            job_location=self.job_location.text().strip(),
            keyword=self.keyword.text().strip() or None,
            max_runs=max_runs_value,
            single_job_url=single_job_url,
            include_recommendations=self.include_recommendations.isChecked(),
            include_new_to_you=self.include_new_to_you.isChecked(),
            exit_when_done=self.exit_when_done.isChecked(),
            chrome_debug_port=int(self.chrome_port.text().strip() or 9222),
            chrome_user_data_dir=self.chrome_user_data_dir.text().strip(),
            chrome_path=self.chrome_path.text().strip(),
            seek_url=self.seek_url.text().strip() or "https://www.seek.com.au/",
            chatgpt_url=self.chatgpt_url.text().strip() or "https://chat.openai.com/",
            chatgpt_chat_title=self.chatgpt_chat_title.text().strip(),
            enable_local_sync=self.enable_local_sync.isChecked(),
            local_sync_path=self.local_sync_path.text().strip(),
            local_sync_pull_before_run=self.local_sync_pull_before_run.isChecked(),
            enable_pdf_export=self.enable_pdf_export.isChecked(),
            skip_title_contains=self.skip_title_contains.text().strip(),
            delay_between_jobs_min_sec=int(self.delay_min.text().strip() or "10"),
            delay_between_jobs_max_sec=int(self.delay_max.text().strip() or "20"),
            batch_size=1,
            pdf_css_path="",
            pdf_output_dir="pdf_output",
            pdf_template_path="templates/navy-gold-template.html",
            user_address=self.user_address.text().strip(),
            user_phone=self.user_phone.text().strip(),
            user_email=self.user_email.text().strip(),
            user_name=self.user_name.text().strip() or "carl chen",
            resume_style=self.resume_style.currentText().strip() or RESUME_STYLE_OPTIONS[0],
            cover_letter_style=self.cover_letter_style.currentText().strip()
            or COVER_LETTER_STYLE_OPTIONS[0],
        )

    def save(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        self.signals.status.emit("Saved")
        self.signals.summary.emit("Config saved.")
        QMessageBox.information(self, "JobFinder", "Config saved.")

    def _set_chrome_ready(self, ready: bool) -> None:
        self.chrome_ready = ready

    def _on_run_action(self) -> None:
        if self.chrome_ready:
            self.start_run()
            return
        if self.launch_chrome():
            self.signals.run_button_text.emit("Continue Run")
            self.signals.chrome_ready.emit(True)

    def launch_chrome(self) -> bool:
        config = self._read_config()
        save_config(CONFIG_PATH, config)
        chrome_path = config.chrome_path.strip()
        if not chrome_path:
            chrome_path = self._detect_chrome_path()
            if chrome_path:
                self.chrome_path.setText(chrome_path)
            else:
                QMessageBox.critical(self, "JobFinder", "Please set Chrome path.")
                return False

        user_dir = config.chrome_user_data_dir.strip()
        if not user_dir:
            user_dir = str(Path.cwd() / "chrome-profile")

        if sys.platform == "darwin":
            return self._launch_chrome_mac(config, chrome_path, user_dir)

        cmd = [
            chrome_path,
            f"--remote-debugging-port={config.chrome_debug_port}",
            f"--user-data-dir={user_dir}",
            "--new-window",
            config.seek_url or "https://www.seek.com.au/",
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0
        try:
            proc = subprocess.Popen(cmd, creationflags=creationflags)
            self.chrome_processes.append(proc)
            self.log_message("Chrome Debug launched.")
        except PermissionError:
            if sys.platform == "win32":
                start_cmd = ["cmd", "/c", "start", "/b", "", chrome_path] + cmd[1:]
                subprocess.Popen(start_cmd, creationflags=creationflags)
                self.log_message("Chrome launched via start.")
            else:
                raise
        except FileNotFoundError:
            QMessageBox.critical(self, "JobFinder", "Chrome executable not found.")
            return False

        self.signals.status.emit("Launching")
        self.signals.summary.emit("Opening Seek and ChatGPT. Log in there, then click Continue Run.")

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
                self.log_message("ChatGPT tab opened.")
            except Exception as exc:
                self.log_message(f"Failed to open ChatGPT tab: {exc}")
                return

            time.sleep(4)
            cleared = clear_chatgpt_draft_via_debugger(config, log=self.log_message)
            self.signals.status.emit("Ready")
            if cleared:
                self.signals.summary.emit("Seek and ChatGPT opened. Finish login, then click Continue Run.")
            else:
                self.signals.summary.emit("Browser is ready. Finish login, then click Continue Run.")

        threading.Thread(target=open_chatgpt_tab, daemon=True).start()
        self.log_message("Attempted to open Seek and ChatGPT tabs.")
        return True

    def _launch_chrome_mac(self, config: Config, chrome_path: str, user_dir: str) -> bool:
        app_bundle = self._chrome_app_bundle_path(chrome_path)
        if not app_bundle:
            QMessageBox.critical(
                self,
                "JobFinder",
                "On macOS, please set Chrome path to the Google Chrome app bundle or executable inside it.",
            )
            return False

        seek_url = config.seek_url or "https://www.seek.com.au/"
        cmd = [
            "open",
            "-na",
            app_bundle,
            "--args",
            f"--remote-debugging-port={config.chrome_debug_port}",
            f"--user-data-dir={user_dir}",
            "--new-window",
            "about:blank",
        ]

        try:
            proc = subprocess.Popen(cmd)
            self.chrome_processes.append(proc)
            self.log_message("Chrome Debug launched on macOS.")
        except FileNotFoundError:
            QMessageBox.critical(self, "JobFinder", "Google Chrome app bundle not found.")
            return False

        self.signals.status.emit("Launching")
        self.signals.summary.emit("Opening Seek and ChatGPT. Log in there, then click Continue Run.")

        def finalize_browser_setup() -> None:
            time.sleep(3)
            tabs_opened = self._open_seek_and_chatgpt_tabs_mac(config)
            time.sleep(4)
            cleared = clear_chatgpt_draft_via_debugger(config, log=self.log_message)
            self.signals.status.emit("Ready")
            if tabs_opened and cleared:
                self.signals.summary.emit("Seek and ChatGPT opened. Finish login, then click Continue Run.")
            elif tabs_opened:
                self.signals.summary.emit("Seek and ChatGPT tabs opened. Finish login, then click Continue Run.")
            else:
                self.signals.summary.emit("Browser is ready. Finish login, then click Continue Run.")

        threading.Thread(target=finalize_browser_setup, daemon=True).start()
        self.log_message("Launched Chrome on macOS and queued Seek + ChatGPT tabs.")
        return True

    def _open_seek_and_chatgpt_tabs_mac(self, config: Config) -> bool:
        seek_url = config.seek_url or "https://www.seek.com.au/"
        chatgpt_url = config.chatgpt_url or "https://chat.openai.com/"
        script = [
            'tell application "Google Chrome"',
            "activate",
            "if (count of windows) = 0 then make new window",
            f'set URL of active tab of front window to "{seek_url}"',
            f'make new tab at end of tabs of front window with properties {{URL:\"{chatgpt_url}\"}}',
            "set active tab index of front window to 1",
            "end tell",
        ]
        try:
            subprocess.run(["osascript", *sum([["-e", line] for line in script], [])], check=True)
            self.log_message("Seek and ChatGPT tabs opened on macOS.")
            return True
        except Exception as exc:
            self.log_message(f"Failed to open Seek and ChatGPT tabs on macOS: {exc}")
            return False

    def start_run(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        exit_when_done = bool(self.config.exit_when_done)
        self.signals.status.emit("Running")
        self.signals.summary.emit("Automation started.")
        self.signals.run_button_enabled.emit(False)

        def worker() -> None:
            try:
                run_web_flow(
                    self.config,
                    log=self.log_message,
                    include_landing_recommendations=self.config.include_recommendations,
                    include_new_to_you=self.config.include_new_to_you,
                )
                self.log_message("Completed.")
                self.signals.status.emit("Completed")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Launch Another Run")
                self.signals.chrome_ready.emit(False)
                if exit_when_done:
                    self.close()
            except Exception as exc:
                self.log_message(f"Error: {exc}")
                self.signals.status.emit("Error")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Continue Run")

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

    def _chrome_app_bundle_path(self, chrome_path: str) -> Optional[str]:
        path = Path(chrome_path)
        if path.suffix == ".app" and path.exists():
            return str(path)

        text = str(path)
        marker = ".app/"
        if marker in text:
            return text.split(marker, 1)[0] + ".app"
        return None

    def edit_skill_file(self) -> None:
        path = Path(ensure_skill_profile_file(str(Path.cwd() / "skill.md")))
        self._open_path(path)

    def edit_prompt_file(self) -> None:
        path = Path(ensure_prompt_template_file(str(Path.cwd() / "prompt.md")))
        self._open_path(path)

    def open_output_folder(self) -> None:
        config = self._read_config()
        output_path = Path(config.output_excel).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path

        target_dir = output_path.parent if output_path.parent != Path("") else Path.cwd()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(target_dir)

    def _open_path(self, path: Path) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def log_message(self, message: str) -> None:
        self.signals.log.emit(message)

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.summary_value.setText(message[:140])

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._close_chrome_processes()
        super().closeEvent(event)

    def _close_chrome_processes(self) -> None:
        for proc in list(self.chrome_processes):
            if proc and proc.poll() is None:
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            capture_output=True,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        )
                    else:
                        proc.terminate()
                except Exception:
                    pass


def main() -> None:
    app = QApplication(sys.argv)
    window = JobFinderWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
