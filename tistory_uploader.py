"""마크다운 변환과 재연결 가능한 티스토리 Chrome 자동화."""

import base64
import json
import os
import re
import socket
import time
import urllib.parse
import urllib.request

import markdown
from selenium import webdriver
from selenium.common.exceptions import WebDriverException


APP_SUPPORT_DIR = os.path.join(
    os.path.expanduser("~"), "Library", "Application Support", "TistoryUploader"
)
# 앱 번들을 다시 만들거나 폴더를 옮겨도 로그인 세션이 유지되는 위치다.
PROFILE_DIR = os.environ.get(
    "TISTORY_UPLOADER_PROFILE", os.path.join(APP_SUPPORT_DIR, "chrome-profile")
)
# 기존 개발용 자동화 Chrome과 완전히 분리된 앱 전용 포트다.
DEBUG_PORT = 19224


def convert_md_to_html(md_text, title, image_loader):
    def replace_image(match):
        alt_text, raw_path = match.group(1), match.group(2)
        image_path = urllib.parse.unquote(raw_path)
        image_bytes = image_loader(image_path)
        if image_bytes is None:
            return match.group(0)
        extension = os.path.splitext(image_path)[1].lower()
        mime = {
            ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
            ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml",
        }.get(extension, "image/png")
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f'<img src="data:{mime};base64,{encoded}" alt="{alt_text}" />'

    converted = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", replace_image, md_text)
    return title, markdown.markdown(converted, extensions=["fenced_code", "tables", "codehilite", "nl2br"])


def convert_md_to_html_with_images(md_file_path):
    folder = os.path.dirname(md_file_path)
    with open(md_file_path, "r", encoding="utf-8-sig") as source:
        md_text = source.read()

    def load_image(relative_path):
        image_path = os.path.normpath(os.path.join(folder, relative_path))
        if not os.path.isfile(image_path):
            return None
        with open(image_path, "rb") as image_file:
            return image_file.read()

    title = os.path.splitext(os.path.basename(md_file_path))[0]
    return convert_md_to_html(md_text, title, load_image)


def _port_open():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
        connection.settimeout(0.2)
        return connection.connect_ex(("127.0.0.1", DEBUG_PORT)) == 0


def _attach_to_existing_chrome():
    options = webdriver.ChromeOptions()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    return webdriver.Chrome(options=options)


def _ensure_page_exists():
    """원격 디버깅 Chrome에 탭이 없을 때 제어 가능한 빈 탭을 만든다."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=2) as response:
            pages = json.load(response)
        if any(page.get("type") == "page" for page in pages):
            return
        request = urllib.request.Request(
            f"http://127.0.0.1:{DEBUG_PORT}/json/new?about:blank", method="PUT"
        )
        with urllib.request.urlopen(request, timeout=2):
            pass
    except Exception as exc:
        raise RuntimeError(f"자동화 크롬 탭을 준비할 수 없습니다: {exc}") from exc


def _remove_stale_locks():
    """Chrome가 종료된 뒤 남은 잠금 링크만 제거한다. 프로필 데이터는 보존한다."""
    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = os.path.join(PROFILE_DIR, name)
        try:
            if os.path.lexists(path):
                os.unlink(path)
        except OSError:
            pass


def _profile_is_in_use():
    """현재 프로필을 쓰는 Chrome가 있으면 잠금 파일을 절대 지우지 않는다."""
    try:
        import subprocess
        output = subprocess.check_output(["ps", "-ax", "-o", "command="], text=True)
    except Exception:
        return False
    expected = f"--user-data-dir={PROFILE_DIR}"
    # 명령행에 프로필 경로라는 문자열만 포함한 셸/테스트 프로세스는 제외한다.
    return any("Google Chrome" in line and expected in line for line in output.splitlines())


def get_or_launch_chrome(current_driver=None):
    """기존 자동화 Chrome에 재연결하거나 최초 한 번만 새로 시작한다."""
    if current_driver is not None:
        try:
            _ = current_driver.current_url
            return current_driver
        except WebDriverException:
            pass

    if _port_open():
        try:
            _ensure_page_exists()
            return _attach_to_existing_chrome()
        except WebDriverException as exc:
            raise RuntimeError(f"기존 자동화 크롬에 연결할 수 없습니다: {exc}") from exc

    if _profile_is_in_use():
        raise RuntimeError(
            "이전 버전의 자동화 크롬이 아직 실행 중입니다. 한 번만 해당 창을 닫고 다시 실행해 주세요. "
            "이후에는 같은 창에 자동으로 재연결됩니다."
        )

    os.makedirs(PROFILE_DIR, exist_ok=True)
    _remove_stale_locks()
    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)
    options.add_argument(f"--user-data-dir={PROFILE_DIR}")
    options.add_argument(f"--remote-debugging-port={DEBUG_PORT}")
    options.add_argument("--remote-debugging-address=127.0.0.1")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    options.add_argument("about:blank")
    try:
        return webdriver.Chrome(options=options)
    except WebDriverException as exc:
        raise RuntimeError(
            "자동화 크롬을 시작하지 못했습니다. Chrome을 업데이트한 뒤 다시 실행해 주세요. "
            f"(세부 원인: {exc.msg})"
        ) from exc


def inject_content(driver, title, html_body, timeout=300):
    """티스토리 편집기가 나타날 때까지 기다렸다가 제목과 본문을 자동 입력한다."""
    end_time = time.monotonic() + timeout
    title_selector = "#post-title-inp, input[name='title'], textarea[name='title']"
    while time.monotonic() < end_time:
        try:
            result = driver.execute_script(
                """
                const titleSelector = arguments[0], title = arguments[1], html = arguments[2];
                const documents = [document, ...[...document.querySelectorAll('iframe')]
                    .map(frame => { try { return frame.contentDocument; } catch (_) { return null; } })
                    .filter(Boolean)];
                const titleInput = document.querySelector(titleSelector);
                const editor = documents.map(doc => doc.querySelector(
                    '.ProseMirror[contenteditable="true"], [contenteditable="true"][role="textbox"], .editor-content[contenteditable="true"], [contenteditable="true"]'
                )).find(Boolean);
                if (!titleInput || !(editor || (window.tinymce && tinymce.activeEditor))) return 'not-ready';
                const proto = titleInput instanceof HTMLTextAreaElement
                    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                Object.getOwnPropertyDescriptor(proto, 'value').set.call(titleInput, title);
                titleInput.dispatchEvent(new Event('input', {bubbles: true}));
                titleInput.dispatchEvent(new Event('change', {bubbles: true}));
                if (window.tinymce && tinymce.activeEditor) {
                    tinymce.activeEditor.setContent(html); tinymce.activeEditor.fire('change');
                } else {
                    editor.focus(); editor.innerHTML = html;
                    editor.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
                    editor.dispatchEvent(new Event('change', {bubbles: true}));
                }
                return 'done';
                """,
                title_selector, title, html_body,
            )
            if result == "done":
                return True
        except WebDriverException:
            # 로그인 과정이나 탭 복구 뒤에는 기존 Selenium 연결이 무효화될 수 있다.
            # 같은 원격 Chrome에 다시 붙여서 대기 작업을 계속한다.
            try:
                driver = get_or_launch_chrome()
            except RuntimeError:
                pass
        time.sleep(1)
    return False
