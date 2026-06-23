import os
import socket
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
    QScrollArea,
    QInputDialog,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from jobfinder_core import (
    COVER_LETTER_DESIGN_OPTIONS,
    COVER_LETTER_STYLE_OPTIONS,
    DEFAULT_COVER_LETTER_DESIGN,
    Config,
    create_profile,
    delete_profile,
    RESUME_STYLE_OPTIONS,
    ensure_prompt_template_file,
    ensure_skill_profile_file,
    load_app_config,
    load_profile_config,
    rename_profile,
    save_app_config,
    save_profile_config,
)
from jobfinder_web import (
    clear_chatgpt_draft_via_debugger,
    connect_driver,
    ensure_seek_and_chatgpt_tabs,
    wait_for_seek_and_chatgpt_ready,
    run_web_flow,
)


CONFIG_PATH = "config.json"
FIELD_MIN_HEIGHT = 48
FIELD_MIN_WIDTH = 420
FORM_LABEL_MIN_WIDTH = 180


class UiSignals(QObject):
    log = Signal(str)
    status = Signal(str)
    summary = Signal(str)
    run_button_text = Signal(str)
    run_button_enabled = Signal(bool)
    chrome_ready = Signal(bool)
    open_outputs = Signal()
    exit_app = Signal()
    edit_single_cover_letter = Signal(object)


class JobFinderWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JobFinder")
        self.resize(1120, 860)
        self.setMinimumSize(920, 720)

        self.app_config = load_app_config(CONFIG_PATH)
        self.config = load_profile_config(self.app_config, config_path=CONFIG_PATH)
        self.chrome_processes = []
        self.signals = UiSignals()
        self.chrome_ready = False
        self._profile_tab_guard = False

        self._build_ui()
        self.signals.log.connect(self._append_log)
        self.signals.status.connect(self.status_value.setText)
        self.signals.summary.connect(self.summary_value.setText)
        self.signals.run_button_text.connect(self.run_action_button.setText)
        self.signals.run_button_enabled.connect(self.run_action_button.setEnabled)
        self.signals.chrome_ready.connect(self._set_chrome_ready)
        self.signals.open_outputs.connect(self.open_generated_outputs)
        self.signals.exit_app.connect(self._exit_app)
        self.signals.edit_single_cover_letter.connect(self._open_single_cover_letter_editor)
        self._load_config_into_form()
        self._setup_placeholders()
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
        root.addWidget(self._build_profile_bar())
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
            "Fill the form and click Run once. On first use, log in to Seek and ChatGPT in the opened browser and JobFinder will continue automatically."
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
        self.profile_value = QLabel("")
        status_layout.addWidget(self.status_value)
        status_layout.addWidget(self.summary_value)
        status_layout.addWidget(self.profile_value)

        layout.addWidget(title, 0, 0)
        layout.addWidget(subtitle, 1, 0)
        layout.addWidget(status_box, 0, 1, 2, 1)
        layout.setColumnStretch(0, 1)
        return frame

    def _build_profile_bar(self) -> QWidget:
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        label = QLabel("Profiles")
        label.setMinimumWidth(60)

        self.profile_tabs = QTabBar()
        self.profile_tabs.setExpanding(False)
        self.profile_tabs.currentChanged.connect(self._on_profile_tab_changed)

        self.add_profile_button = QPushButton("New Profile")
        self.add_profile_button.clicked.connect(self.add_profile)

        self.rename_profile_button = QPushButton("Rename")
        self.rename_profile_button.clicked.connect(self.rename_active_profile)

        self.delete_profile_button = QPushButton("Delete")
        self.delete_profile_button.clicked.connect(self.delete_active_profile)

        layout.addWidget(label)
        layout.addWidget(self.profile_tabs, 1)
        layout.addWidget(self.add_profile_button)
        layout.addWidget(self.rename_profile_button)
        layout.addWidget(self.delete_profile_button)
        self._reload_profile_tabs()
        return frame

    def _build_actions(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.run_action_button = QPushButton("Run JobFinder")
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
        self.tabs.addTab(self._wrap_scroll(self._build_basic_tab()), "Basic")
        self.tabs.addTab(self._wrap_scroll(self._build_advanced_tab()), "Advanced")
        self.tabs.addTab(self._wrap_scroll(self._build_personal_tab()), "Personal")
        self.tabs.addTab(self._wrap_scroll(self._build_notes_tab()), "Run Notes")
        return self.tabs

    def _wrap_scroll(self, widget: QWidget) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(widget)
        return scroll

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
        outer.setSpacing(14)

        top_row = QHBoxLayout()
        top_row.setSpacing(14)
        top_row.addWidget(
            self._group_with_form(
                "Writing Style & Run Behavior",
                [
                    ("Resume Style", self._combo("resume_style", RESUME_STYLE_OPTIONS)),
                    (
                        "Cover Letter Style",
                        self._combo("cover_letter_style", COVER_LETTER_STYLE_OPTIONS),
                    ),
                    (
                        "Cover Letter Design",
                        self._combo("cover_letter_design", COVER_LETTER_DESIGN_OPTIONS),
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
        top_row.addWidget(
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
        outer.addLayout(top_row)

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
            "1. Click Run JobFinder once.",
            "2. If this is your first app-wide login, sign in to Seek and ChatGPT in the opened browser tabs.",
            "3. Wait for both Seek and ChatGPT to finish loading.",
            "4. JobFinder will continue automatically and keep the button disabled while running.",
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

    def _reload_profile_tabs(self) -> None:
        self._profile_tab_guard = True
        try:
            while self.profile_tabs.count() > 0:
                self.profile_tabs.removeTab(0)
            current_index = 0
            for index, profile in enumerate(self.app_config.profiles):
                self.profile_tabs.addTab(profile.label)
                self.profile_tabs.setTabData(index, profile.id)
                if profile.id == self.app_config.active_profile_id:
                    current_index = index
            self.profile_tabs.setCurrentIndex(current_index)
            self._update_profile_label()
        finally:
            self._profile_tab_guard = False

    def _update_profile_label(self) -> None:
        self.profile_value.setText(f"Profile: {self.config.profile_label}")

    def _active_profile_id(self) -> str:
        index = self.profile_tabs.currentIndex()
        if index < 0:
            return self.app_config.active_profile_id
        tab_data = self.profile_tabs.tabData(index)
        return str(tab_data) if tab_data else self.app_config.active_profile_id

    def _save_current_profile(self, show_message: bool = False) -> Config:
        config = self._read_config()
        self.config = config
        self.app_config.active_profile_id = config.profile_id
        self.app_config.chrome_debug_port = config.chrome_debug_port
        self.app_config.chrome_user_data_dir = config.chrome_user_data_dir
        self.app_config.chrome_path = config.chrome_path
        save_app_config(CONFIG_PATH, self.app_config)
        save_profile_config(self.app_config, config, profile_id=config.profile_id, config_path=CONFIG_PATH)
        self._update_profile_label()
        if show_message:
            self.signals.status.emit("Saved")
            self.signals.summary.emit(f"Saved profile: {config.profile_label}")
            QMessageBox.information(self, "JobFinder", f"Saved profile: {config.profile_label}")
        return config

    def _switch_to_profile(self, profile_id: str) -> None:
        self.app_config.active_profile_id = profile_id
        save_app_config(CONFIG_PATH, self.app_config)
        self.config = load_profile_config(self.app_config, profile_id=profile_id, config_path=CONFIG_PATH)
        self._load_config_into_form()
        self._setup_placeholders()
        self._update_profile_label()

    def _on_profile_tab_changed(self, index: int) -> None:
        if self._profile_tab_guard or index < 0:
            return
        profile_id = self._active_profile_id()
        if profile_id == self.config.profile_id:
            return
        self._save_current_profile()
        self._switch_to_profile(profile_id)

    def add_profile(self) -> None:
        label, ok = QInputDialog.getText(self, "New Profile", "Profile name:")
        if not ok:
            return
        name = label.strip()
        if not name:
            return
        self._save_current_profile()
        profile = create_profile(self.app_config, name, config_path=CONFIG_PATH)
        self.app_config = load_app_config(CONFIG_PATH)
        self._reload_profile_tabs()
        self._profile_tab_guard = True
        try:
            for index in range(self.profile_tabs.count()):
                if str(self.profile_tabs.tabData(index)) == profile.id:
                    self.profile_tabs.setCurrentIndex(index)
                    break
        finally:
            self._profile_tab_guard = False
        self._switch_to_profile(profile.id)

    def rename_active_profile(self) -> None:
        current_id = self.config.profile_id
        label, ok = QInputDialog.getText(
            self,
            "Rename Profile",
            "Profile name:",
            text=self.config.profile_label,
        )
        if not ok:
            return
        name = label.strip()
        if not name:
            return
        self._save_current_profile()
        rename_profile(self.app_config, current_id, name, config_path=CONFIG_PATH)
        self.app_config = load_app_config(CONFIG_PATH)
        self.config = load_profile_config(self.app_config, profile_id=current_id, config_path=CONFIG_PATH)
        self._reload_profile_tabs()
        self._load_config_into_form()
        self._update_profile_label()

    def delete_active_profile(self) -> None:
        if len(self.app_config.profiles) <= 1:
            QMessageBox.warning(self, "JobFinder", "At least one profile must remain.")
            return
        profile_label = self.config.profile_label
        should_delete = QMessageBox.question(
            self,
            "Delete Profile",
            f"Delete profile '{profile_label}' and its files?",
        )
        if should_delete != QMessageBox.Yes:
            return
        current_id = self.config.profile_id
        delete_profile(self.app_config, current_id, config_path=CONFIG_PATH)
        self.app_config = load_app_config(CONFIG_PATH)
        self.config = load_profile_config(self.app_config, config_path=CONFIG_PATH)
        self._reload_profile_tabs()
        self._load_config_into_form()
        self._setup_placeholders()
        self._update_profile_label()

    def _group_with_form(self, title: str, rows, checkboxes=None) -> QWidget:
        group = QGroupBox(title)
        layout = QVBoxLayout(group)
        group.setMinimumHeight(220)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)
        for label, widget in rows:
            label_widget = QLabel(label)
            label_widget.setMinimumWidth(FORM_LABEL_MIN_WIDTH)
            label_widget.setWordWrap(True)
            label_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            form.addRow(label_widget, widget)
        layout.addLayout(form)

        if checkboxes:
            for label, checkbox in checkboxes:
                checkbox.setText(label)
                layout.addWidget(checkbox)

        return group

    def _line(self, name: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setMinimumWidth(FIELD_MIN_WIDTH)
        widget.setMinimumHeight(FIELD_MIN_HEIGHT)
        widget.setMaximumHeight(FIELD_MIN_HEIGHT + 8)
        setattr(self, name, widget)
        return widget

    def _combo(self, name: str, values) -> QComboBox:
        combo = QComboBox()
        combo.addItems(list(values))
        combo.setEditable(False)
        combo.setMinimumWidth(FIELD_MIN_WIDTH)
        combo.setMinimumHeight(FIELD_MIN_HEIGHT)
        combo.setMaximumHeight(FIELD_MIN_HEIGHT + 8)
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
        wrapper.setMinimumHeight(FIELD_MIN_HEIGHT)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        edit = QLineEdit()
        edit.setMinimumWidth(FIELD_MIN_WIDTH)
        edit.setMinimumHeight(FIELD_MIN_HEIGHT)
        edit.setMaximumHeight(FIELD_MIN_HEIGHT + 8)
        setattr(self, name, edit)
        button = QPushButton("Browse")
        button.setMinimumHeight(FIELD_MIN_HEIGHT)
        button.setMaximumHeight(FIELD_MIN_HEIGHT + 8)
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
        self.chrome_port.setText(str(self.app_config.chrome_debug_port))
        self.chrome_user_data_dir.setText(self.app_config.chrome_user_data_dir)
        self.chrome_path.setText(self.app_config.chrome_path)
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
        self.cover_letter_design.setCurrentText(
            getattr(cfg, "cover_letter_design", DEFAULT_COVER_LETTER_DESIGN)
        )
        self.skip_title_contains.setText(getattr(cfg, "skip_title_contains", "") or "")
        self.delay_min.setText(str(getattr(cfg, "delay_between_jobs_min_sec", 10)))
        self.delay_max.setText(str(getattr(cfg, "delay_between_jobs_max_sec", 20)))

    def _setup_placeholders(self) -> None:
        if self.job_location.text().strip() == "All Gold Coast QLD":
            self.job_location.clear()
            self.job_location.setPlaceholderText("All Gold Coast QLD")

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
            cover_letter_design=self.cover_letter_design.currentText().strip()
            or DEFAULT_COVER_LETTER_DESIGN,
            skill_profile_path=self.config.skill_profile_path,
            prompt_template_path=self.config.prompt_template_path,
            profile_id=self.config.profile_id,
            profile_label=self.config.profile_label,
        )

    def save(self) -> None:
        self._save_current_profile(show_message=True)

    def _set_chrome_ready(self, ready: bool) -> None:
        self.chrome_ready = ready

    def _on_run_action(self) -> None:
        config = self._resolve_launch_config()
        if config is None:
            return
        self.signals.run_button_enabled.emit(False)
        self.signals.run_button_text.emit("Preparing Browser...")
        self.signals.status.emit("Preparing")
        if self.app_config.initial_login_completed:
            self.signals.summary.emit("Checking Seek and ChatGPT tabs, then starting the run.")
        else:
            self.signals.summary.emit("Opening Seek and ChatGPT. Log in once and JobFinder will continue automatically.")
        threading.Thread(target=lambda: self._prepare_and_start_run(config), daemon=True).start()

    def _resolve_launch_config(self) -> Optional[Config]:
        config = self._save_current_profile()
        chrome_path = config.chrome_path.strip()
        if not chrome_path:
            chrome_path = self._detect_chrome_path() or ""
            if chrome_path:
                self.chrome_path.setText(chrome_path)
                config.chrome_path = chrome_path
                self.config = config
                save_app_config(CONFIG_PATH, self.app_config)
                save_profile_config(self.app_config, config, profile_id=config.profile_id, config_path=CONFIG_PATH)
            else:
                QMessageBox.critical(self, "JobFinder", "Please set Chrome path.")
                return None
        if sys.platform == "darwin" and not self._chrome_app_bundle_path(chrome_path):
            QMessageBox.critical(
                self,
                "JobFinder",
                "On macOS, please set Chrome path to the Google Chrome app bundle or executable inside it.",
            )
            return None
        return config

    def _prepare_and_start_run(self, config: Config) -> None:
        try:
            launched = self.launch_chrome(config=config, auto_continue=True)
            if not launched:
                self.signals.status.emit("Idle")
                self.signals.summary.emit("Chrome launch was cancelled.")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Run JobFinder")
        except Exception as exc:
            self.log_message(f"Browser preparation failed: {exc}")
            self.signals.status.emit("Error")
            self.signals.summary.emit("Could not prepare the browser.")
            self.signals.run_button_enabled.emit(True)
            self.signals.run_button_text.emit("Run JobFinder")

    def launch_chrome(self, config: Optional[Config] = None, auto_continue: bool = False) -> bool:
        config = config or self._save_current_profile()
        chrome_path = config.chrome_path.strip()
        if not chrome_path:
            chrome_path = self._detect_chrome_path() or ""
            if not chrome_path:
                self.log_message("Chrome path is not set.")
                return False

        user_dir = config.chrome_user_data_dir.strip()
        if not user_dir:
            user_dir = str(Path.cwd() / "chrome-profile")

        if self._debug_port_is_open(config.chrome_debug_port):
            self.log_message(f"Detected existing Chrome debug port on {config.chrome_debug_port}.")
            if self._attach_to_existing_browser(config, auto_continue=auto_continue):
                return True
            self.log_message("Debug port responded but attach failed. Launching a fresh Chrome window.")

        if sys.platform == "darwin":
            return self._launch_chrome_mac(config, chrome_path, user_dir, auto_continue=auto_continue)

        cmd = [
            chrome_path,
            f"--remote-debugging-port={config.chrome_debug_port}",
            f"--user-data-dir={user_dir}",
            "--new-window",
            "about:blank",
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
        if self.app_config.initial_login_completed:
            self.signals.summary.emit("Opening Seek and ChatGPT tabs and waiting for them to load.")
        else:
            self.signals.summary.emit("Opening Seek and ChatGPT tabs. Please log in once when prompted.")

        threading.Thread(
            target=lambda: self._finish_browser_preparation(config, auto_continue=auto_continue, launch_delay=2),
            daemon=True,
        ).start()
        self.log_message("Attempted to open Seek and ChatGPT tabs.")
        return True

    def _debug_port_is_open(self, port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", int(port)), timeout=1):
                return True
        except Exception:
            return False

    def _launch_chrome_mac(
        self,
        config: Config,
        chrome_path: str,
        user_dir: str,
        auto_continue: bool = False,
    ) -> bool:
        app_bundle = self._chrome_app_bundle_path(chrome_path)
        if not app_bundle:
            self.log_message("Chrome app bundle could not be resolved on macOS.")
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
            self.log_message("Google Chrome app bundle not found.")
            return False

        self.signals.status.emit("Launching")
        if self.app_config.initial_login_completed:
            self.signals.summary.emit("Opening Seek and ChatGPT tabs and waiting for them to load.")
        else:
            self.signals.summary.emit("Opening Seek and ChatGPT tabs. Please log in once when prompted.")

        threading.Thread(
            target=lambda: self._finish_browser_preparation(
                config,
                auto_continue=auto_continue,
                launch_delay=3,
                open_tabs_first=True,
            ),
            daemon=True,
        ).start()
        self.log_message("Launched Chrome on macOS and queued Seek + ChatGPT tabs.")
        return True

    def _attach_to_existing_browser(self, config: Config, auto_continue: bool = False) -> bool:
        driver = None
        try:
            driver = connect_driver(config)
            ensure_seek_and_chatgpt_tabs(driver, config)
            self.log_message("Attached to existing Chrome debug session.")
        except Exception:
            return False
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        self.signals.status.emit("Preparing")
        self.signals.summary.emit("Using existing browser session and checking readiness.")
        threading.Thread(
            target=lambda: self._finish_browser_preparation(config, auto_continue=auto_continue, launch_delay=0),
            daemon=True,
        ).start()
        return True

    def _finish_browser_preparation(
        self,
        config: Config,
        auto_continue: bool,
        launch_delay: int = 0,
        open_tabs_first: bool = False,
    ) -> None:
        if launch_delay > 0:
            time.sleep(launch_delay)

        if open_tabs_first and not self._open_seek_and_chatgpt_tabs_mac(config):
            self.log_message("Falling back to debugger-based tab check on macOS.")

        driver = None
        try:
            driver = connect_driver(config)
            seek_handle, _ = ensure_seek_and_chatgpt_tabs(driver, config)
            driver.switch_to.window(seek_handle)
            self.log_message("Seek and ChatGPT opened in separate tabs.")
        except Exception as exc:
            self.log_message(f"Failed to open Seek and ChatGPT tabs: {exc}")
            self.signals.status.emit("Error")
            self.signals.summary.emit("Could not open both browser tabs.")
            self.signals.run_button_enabled.emit(True)
            self.signals.run_button_text.emit("Run JobFinder")
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
            return
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        clear_chatgpt_draft_via_debugger(config, log=self.log_message)
        if auto_continue:
            self._wait_for_browser_and_start(config)
            return

        self.signals.status.emit("Ready")
        self.signals.summary.emit("Browser is ready.")

    def _wait_for_browser_and_start(self, config: Config) -> None:
        wait_timeout = 900 if not self.app_config.initial_login_completed else 180
        if self.app_config.initial_login_completed:
            self.signals.status.emit("Preparing")
            self.signals.summary.emit("Waiting for Seek and ChatGPT to finish loading.")
        else:
            self.signals.status.emit("Waiting For Login")
            self.signals.summary.emit("Log in to Seek and ChatGPT in the opened tabs. JobFinder will continue automatically.")

        driver = None
        try:
            driver = connect_driver(config)
            ready = wait_for_seek_and_chatgpt_ready(driver, config, timeout=wait_timeout, log=self.log_message)
            if not ready:
                self.signals.status.emit("Login Required")
                self.signals.summary.emit("Could not confirm Seek and ChatGPT are ready yet.")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Run JobFinder")
                return
        except Exception as exc:
            self.log_message(f"Readiness check failed: {exc}")
            self.signals.status.emit("Error")
            self.signals.summary.emit("Could not verify browser readiness.")
            self.signals.run_button_enabled.emit(True)
            self.signals.run_button_text.emit("Run JobFinder")
            return
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        if not self.app_config.initial_login_completed:
            self.app_config.initial_login_completed = True
            save_app_config(CONFIG_PATH, self.app_config)
            self.log_message("Initial app-wide login completed.")

        self.signals.status.emit("Running")
        self.signals.summary.emit("Seek and ChatGPT are ready. Starting automation.")
        self.start_run(prepared_config=config)

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

    def start_run(self, prepared_config: Optional[Config] = None) -> None:
        self.config = prepared_config or self._save_current_profile()
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
                    review_single_cover_letter=(
                        self._request_single_cover_letter_edit if self.config.single_job_url else None
                    ),
                )
                self.log_message("Completed.")
                self.signals.status.emit("Completed")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Run JobFinder")
                self.signals.chrome_ready.emit(False)
                if exit_when_done:
                    self.signals.summary.emit("Run completed. Closing JobFinder.")
                    self.signals.exit_app.emit()
            except Exception as exc:
                self.log_message(f"Error: {exc}")
                self.signals.status.emit("Error")
                self.signals.run_button_enabled.emit(True)
                self.signals.run_button_text.emit("Run JobFinder")

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

    def _exit_app(self) -> None:
        self.close()

    def _request_single_cover_letter_edit(self, initial_text: str) -> Optional[str]:
        request = {
            "text": initial_text,
            "accepted": False,
            "result_text": initial_text,
            "done": threading.Event(),
        }
        self.signals.edit_single_cover_letter.emit(request)
        request["done"].wait()
        if not request["accepted"]:
            return None
        return str(request["result_text"])

    def _open_single_cover_letter_editor(self, request: object) -> None:
        if not isinstance(request, dict):
            return
        text, ok = QInputDialog.getMultiLineText(
            self,
            "Review Cover Letter",
            "Edit the cover letter before saving:",
            str(request.get("text", "") or ""),
        )
        request["accepted"] = bool(ok)
        request["result_text"] = text if ok else request.get("text", "")
        done = request.get("done")
        if hasattr(done, "set"):
            done.set()

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
        self._save_current_profile()
        path = Path(ensure_skill_profile_file(self.config.skill_profile_path))
        self._open_path(path)

    def edit_prompt_file(self) -> None:
        self._save_current_profile()
        path = Path(ensure_prompt_template_file(self.config.prompt_template_path))
        self._open_path(path)

    def open_output_folder(self) -> None:
        config = self._save_current_profile()
        output_path = Path(config.output_excel).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path

        target_dir = output_path.parent if output_path.parent != Path("") else Path.cwd()
        target_dir.mkdir(parents=True, exist_ok=True)
        self._open_path(target_dir)

    def open_generated_outputs(self) -> None:
        config = self.config
        output_path = Path(config.output_excel).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        if output_path.exists():
            self._open_path(output_path)

        if config.enable_pdf_export:
            pdf_dir = Path(config.pdf_output_dir).expanduser()
            if not pdf_dir.is_absolute():
                pdf_dir = Path.cwd() / pdf_dir
            if pdf_dir.exists():
                self._open_path(pdf_dir)

    def _open_path(self, path: Path) -> None:
        path = path.expanduser()
        if not path.is_absolute():
            path = Path.cwd() / path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def log_message(self, message: str) -> None:
        self.signals.log.emit(message)

    def _append_log(self, message: str) -> None:
        self.log_view.append(message)
        self.summary_value.setText(message[:140])

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self._save_current_profile()
        except Exception:
            pass
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
