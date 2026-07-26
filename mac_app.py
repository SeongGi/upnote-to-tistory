"""티스토리 업로더 macOS 데스크톱 앱."""

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tistory_uploader import (
    APP_SUPPORT_DIR,
    convert_md_to_html_with_images,
    get_or_launch_chrome,
    inject_content,
)


SETTINGS_PATH = Path(APP_SUPPORT_DIR) / "settings.json"


class TistoryUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("티스토리 업로더")
        self.root.geometry("560x350")
        self.root.resizable(False, False)
        self.events = queue.Queue()
        self.driver = None
        self.markdown_path = tk.StringVar()
        self.blog_id = tk.StringVar(value=self._load_blog_id())
        self.status = tk.StringVar(value="마크다운 파일을 선택해 주세요.")
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(100, self._drain_events)

    def _build_ui(self):
        frame = ttk.Frame(self.root, padding=24)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="티스토리 업로더", font=("Apple SD Gothic Neo", 22, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="마크다운을 선택하면 Chrome에서 로그인 후 본문이 자동 입력됩니다.",
            foreground="#555555",
        ).pack(anchor="w", pady=(5, 24))

        ttk.Label(frame, text="티스토리 블로그 ID").pack(anchor="w")
        self.blog_entry = ttk.Entry(frame, textvariable=self.blog_id, width=54)
        self.blog_entry.pack(fill="x", pady=(5, 18))

        ttk.Label(frame, text="업로드할 마크다운 파일").pack(anchor="w")
        file_row = ttk.Frame(frame)
        file_row.pack(fill="x", pady=(5, 16))
        ttk.Entry(file_row, textvariable=self.markdown_path, state="readonly").pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(file_row, text="파일 선택…", command=self.choose_file).pack(side="left", padx=(8, 0))

        self.upload_button = ttk.Button(frame, text="업로드 시작", command=self.start_upload)
        self.upload_button.pack(fill="x", ipady=7)
        ttk.Separator(frame).pack(fill="x", pady=18)
        ttk.Label(frame, textvariable=self.status, wraplength=510, justify="left").pack(anchor="w")

    def _load_blog_id(self):
        try:
            with SETTINGS_PATH.open(encoding="utf-8") as settings_file:
                return json.load(settings_file).get("blog_id", "")
        except (OSError, json.JSONDecodeError):
            return ""

    def _save_blog_id(self):
        Path(APP_SUPPORT_DIR).mkdir(parents=True, exist_ok=True)
        with SETTINGS_PATH.open("w", encoding="utf-8") as settings_file:
            json.dump({"blog_id": self.blog_id.get().strip()}, settings_file, ensure_ascii=False)

    def choose_file(self):
        filename = filedialog.askopenfilename(
            title="업로드할 마크다운 선택",
            filetypes=[("Markdown", "*.md"), ("모든 파일", "*.*")],
        )
        if filename:
            self.markdown_path.set(filename)
            self.status.set(f"선택됨: {os.path.basename(filename)}")

    def start_upload(self):
        blog_id = self.blog_id.get().strip()
        markdown_path = self.markdown_path.get()
        if not blog_id:
            messagebox.showwarning("블로그 ID 필요", "티스토리 블로그 ID를 입력해 주세요.")
            self.blog_entry.focus_set()
            return
        if not os.path.isfile(markdown_path):
            messagebox.showwarning("파일 선택 필요", "업로드할 .md 파일을 선택해 주세요.")
            return

        self._save_blog_id()
        self.upload_button.state(["disabled"])
        self.status.set("마크다운을 변환하는 중입니다…")
        threading.Thread(
            target=self._upload_worker, args=(blog_id, markdown_path), daemon=True
        ).start()

    def _upload_worker(self, blog_id, markdown_path):
        try:
            title, html_body = convert_md_to_html_with_images(markdown_path)
            self.events.put(("status", "자동화 Chrome에 연결하는 중입니다…"))
            self.driver = get_or_launch_chrome(self.driver)
            self.events.put(("status", "티스토리 글쓰기 화면을 여는 중입니다…"))
            self.driver.get(f"https://{blog_id}.tistory.com/manage/post")
            self.events.put(("status", "Chrome에서 로그인이 필요하면 로그인해 주세요. 에디터가 열리면 자동 입력됩니다…"))
            if inject_content(self.driver, title, html_body, timeout=300):
                self.events.put(("done", "입력이 완료되었습니다. Chrome에서 확인 후 [완료]를 눌러 발행하세요."))
            else:
                self.events.put(("error", "5분 안에 편집기를 찾지 못했습니다. 로그인 상태를 확인한 뒤 다시 시도해 주세요."))
        except Exception as exc:
            self.events.put(("error", f"업로드를 시작하지 못했습니다.\n{exc}"))

    def _drain_events(self):
        try:
            while True:
                kind, message = self.events.get_nowait()
                self.status.set(message)
                if kind in {"done", "error"}:
                    self.upload_button.state(["!disabled"])
                    if kind == "done":
                        messagebox.showinfo("입력 완료", message)
                    else:
                        messagebox.showerror("업로드 오류", message)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def close(self):
        self._save_blog_id()
        self.root.destroy()


def main():
    root = tk.Tk()
    TistoryUploaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
