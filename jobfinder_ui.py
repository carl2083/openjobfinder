import os
import subprocess
import sys
import time
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from jobfinder_core import Config, load_config, save_config
from jobfinder_web import run_web_flow


CONFIG_PATH = "config.json"


class JobFinderUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("JobFinder")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.config = load_config(CONFIG_PATH)
        self.chrome_processes = []

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
        self.skip_title_contains = tk.StringVar(
            value=getattr(self.config, "skip_title_contains", "") or ""
        )
        self.delay_min = tk.StringVar(
            value=str(getattr(self.config, "delay_between_jobs_min_sec", 30))
        )
        self.delay_max = tk.StringVar(
            value=str(getattr(self.config, "delay_between_jobs_max_sec", 90))
        )
        self._build_ui()

    def _build_ui(self) -> None:
        main = tk.Frame(self.root, padx=10, pady=10)
        main.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(main)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Tab 1: Basic
        tab_basic = tk.Frame(notebook, padx=8, pady=8)
        notebook.add(tab_basic, text="Basic")
        self._add_labeled_entry(tab_basic, "职位地点", self.job_location, 0)
        self._add_labeled_entry(tab_basic, "关键词", self.keyword, 1)
        self._add_labeled_entry(tab_basic, "运行次数 / JD URL", self.max_runs, 2)
        self._add_checkbox(tab_basic, "优先处理推荐页", self.include_recommendations, 3)
        self._add_checkbox(tab_basic, "优先处理 New to you", self.include_new_to_you, 4)
        self._add_checkbox(tab_basic, "完成之后退出程序", self.exit_when_done, 5)

        # Tab 2: Advanced
        tab_advanced = tk.Frame(notebook, padx=8, pady=8)
        notebook.add(tab_advanced, text="Advanced")
        self._add_labeled_entry(tab_advanced, "Excel 输出文件", self.output_excel, 0)
        self._add_labeled_entry(tab_advanced, "搜索地址 (Seek URL)", self.seek_url, 1)
        self._add_labeled_entry(tab_advanced, "Chrome Debug 端口", self.chrome_port, 2)
        self._add_labeled_entry(
            tab_advanced, "Chrome 用户目录", self.chrome_user_data_dir, 3
        )
        self._add_labeled_entry(tab_advanced, "Chrome 路径", self.chrome_path, 4)
        self._add_labeled_entry(tab_advanced, "ChatGPT URL", self.chatgpt_url, 5)
        self._add_labeled_entry(
            tab_advanced,
            "ChatGPT 对话名称 (留空=用当前对话，避免长对话变慢)",
            self.chatgpt_chat_title,
            6,
        )
        self._add_checkbox(
            tab_advanced, "本地盘符同步(不上传)", self.enable_local_sync, 7
        )
        self._add_labeled_entry(tab_advanced, "同步文件路径", self.local_sync_path, 8)
        self._add_checkbox(
            tab_advanced, "运行前从同步路径读取", self.local_sync_pull_before_run, 9
        )
        self._add_checkbox(
            tab_advanced, "导出简历/求职信 PDF", self.enable_pdf_export, 10
        )
        self._add_labeled_entry(
            tab_advanced,
            "跳过标题包含 (英文或中文逗号分隔)",
            self.skip_title_contains,
            11,
        )
        self._add_labeled_entry(
            tab_advanced,
            "任务间隔秒数 (最小)",
            self.delay_min,
            12,
        )
        self._add_labeled_entry(
            tab_advanced,
            "任务间隔秒数 (最大)",
            self.delay_max,
            13,
        )

        # Tab 3: Personal Info
        tab_personal = tk.Frame(notebook, padx=8, pady=8)
        notebook.add(tab_personal, text="Personal Info")
        self._add_labeled_entry(tab_personal, "地址 (Header)", self.user_address, 0)
        self._add_labeled_entry(tab_personal, "电话 (Header)", self.user_phone, 1)
        self._add_labeled_entry(tab_personal, "Email (Header)", self.user_email, 2)
        self._add_labeled_entry(tab_personal, "姓名 (Header)", self.user_name, 3)

        btn_frame = tk.Frame(main)
        btn_frame.pack(fill=tk.X, pady=4)
        tk.Button(btn_frame, text="保存配置", command=self.save).pack(
            side=tk.LEFT, padx=4
        )
        self.btn_launch_chrome = tk.Button(
            btn_frame, text="启动 Debug Chrome", command=self._on_launch_chrome
        )
        self.btn_launch_chrome.pack(side=tk.LEFT, padx=4)
        self.btn_start_run = tk.Button(
            btn_frame, text="开始运行", command=self.start_run, state=tk.DISABLED
        )
        self.btn_start_run.pack(side=tk.LEFT, padx=4)
        tk.Button(btn_frame, text="编辑 skill.md", command=self.edit_skill_file).pack(
            side=tk.LEFT, padx=4
        )

        self.log = tk.Text(main, height=10)
        self.log.pack(fill=tk.BOTH, expand=True)

    def _add_labeled_entry(
        self, parent: tk.Frame, label: str, var: tk.StringVar, row: int
    ) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        entry = tk.Entry(parent, textvariable=var, width=60)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        if "路径" in label or "文件" in label:
            tk.Button(
                parent,
                text="选择",
                command=lambda: self._select_path(var),
            ).grid(row=row, column=2, padx=4)

    def _select_path(self, var: tk.StringVar) -> None:
        path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def _add_checkbox(
        self, parent: tk.Frame, label: str, var: tk.BooleanVar, row: int
    ) -> None:
        tk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        tk.Checkbutton(parent, variable=var).grid(row=row, column=1, sticky="w", pady=2)

    def log_message(self, message: str) -> None:
        self.log.insert(tk.END, message + "\n")
        self.log.see(tk.END)

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
            delay_between_jobs_min_sec=int(
                self.delay_min.get().strip() or "30"
            ),
            delay_between_jobs_max_sec=int(
                self.delay_max.get().strip() or "90"
            ),
            batch_size=1,
            pdf_css_path="",
            pdf_output_dir="pdf_output",
            pdf_template_path="templates/navy-gold-template.html",
            user_address=self.user_address.get().strip(),
            user_phone=self.user_phone.get().strip(),
            user_email=self.user_email.get().strip(),
            user_name=self.user_name.get().strip() or "carl chen",
        )

    def save(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        messagebox.showinfo("JobFinder", "配置已保存。")

    def _on_launch_chrome(self) -> None:
        if self.launch_chrome():
            self.btn_launch_chrome.config(state=tk.DISABLED)
            self.btn_start_run.config(state=tk.NORMAL)

    def launch_chrome(self) -> bool:
        config = self._read_config()
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
            config.seek_url or "https://www.seek.com.au/",
        ]
        # Windows: 不弹出 CMD 窗口 (Python 3.7+ 有 CREATE_NO_WINDOW)
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
            # 使用 start 规避 WinError 5，且不显示 CMD
            start_cmd = ["cmd", "/c", "start", "/b", "", chrome_path] + cmd[1:]
            subprocess.Popen(start_cmd, creationflags=creationflags)
            self.log_message("已通过 start 启动 Chrome Debug。")
        except FileNotFoundError:
            messagebox.showerror("JobFinder", "找不到 Chrome 可执行文件。")
            return False

        def open_chatgpt_tab():
            time.sleep(1)
            try:
                proc = subprocess.Popen(
                    [
                        chrome_path,
                        f"--remote-debugging-port={config.chrome_debug_port}",
                        f"--user-data-dir={user_dir}",
                        config.chatgpt_url or "https://chat.openai.com/",
                    ],
                    creationflags=creationflags,
                )
                self.chrome_processes.append(proc)
            except Exception:
                pass

        threading.Thread(target=open_chatgpt_tab, daemon=True).start()
        self.log_message("已尝试打开 Seek 和 ChatGPT 标签页。")
        return True


    def start_run(self) -> None:
        self.config = self._read_config()
        save_config(CONFIG_PATH, self.config)
        exit_when_done = bool(self.config.exit_when_done)

        def worker():
            try:
                run_web_flow(
                    self.config,
                    log=self.log_message,
                    include_landing_recommendations=self.config.include_recommendations,
                    include_new_to_you=self.config.include_new_to_you,
                )
                self.log_message("完成。")
                if exit_when_done:
                    self.root.after(0, self.on_close)
            except Exception as exc:  # pragma: no cover - UI error display
                self.log_message(f"错误: {exc}")

        threading.Thread(target=worker, daemon=True).start()

    def _detect_chrome_path(self) -> Optional[str]:
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return None

    def edit_skill_file(self) -> None:
        path = Path.cwd() / "skill.md"
        if not path.exists():
            messagebox.showerror("JobFinder", "找不到 skill.md 文件。")
            return
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showerror("JobFinder", "无法打开 skill.md。")

    def on_close(self) -> None:
        self._close_chrome_processes()
        self.root.destroy()

    def _close_chrome_processes(self) -> None:
        for proc in list(self.chrome_processes):
            if proc and proc.poll() is None:
                try:
                    creationflags = (
                        getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
                        if sys.platform == "win32"
                        else 0
                    )
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        creationflags=creationflags,
                    )
                except Exception:
                    pass


def main() -> None:
    root = tk.Tk()
    root.geometry("820x620")
    JobFinderUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
