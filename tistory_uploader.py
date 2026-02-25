"""
티스토리 자동 업로더 v2
======================
UpNote에서 내보낸 마크다운(.md) 파일과 이미지들을
티스토리 글쓰기 에디터에 자동으로 입력하는 스크립트입니다.

핵심: UI 버튼 클릭 대신 JavaScript로 에디터 API에 직접 주입하여
안정적으로 동작합니다.

* 처음 실행 시 자동으로 가상환경(.venv) 생성 및 패키지 설치가 진행됩니다.
"""

# ──────────────────────────────────────────────
# 자동 환경 설정 (venv 생성 + 패키지 설치)
# ──────────────────────────────────────────────
import sys
import os
import subprocess

REQUIRED_PACKAGES = ["selenium", "webdriver-manager", "pyperclip", "markdown"]

def _bootstrap():
    """가상환경이 아니면 자동으로 생성하고 패키지를 설치한 뒤 재실행합니다."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, ".venv")

    # Windows vs Mac/Linux 경로 분기
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")

    # 이미 가상환경 안에서 실행 중이면 그대로 진행
    if sys.prefix != sys.base_prefix:
        return

    print("=" * 55)
    print("  초기 환경 설정 (최초 1회만 실행됩니다)")
    print("=" * 55)

    # 1) 가상환경 생성 (없을 경우)
    if not os.path.exists(venv_python):
        print("\n>> 가상환경 생성 중... (.venv)")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        print("   완료!")

    # 2) 필수 패키지 설치
    print(">> 필수 패키지 설치 중...")
    subprocess.check_call(
        [venv_python, "-m", "pip", "install", "--upgrade", "pip", "-q"],
    )
    subprocess.check_call(
        [venv_python, "-m", "pip", "install"] + REQUIRED_PACKAGES + ["-q"],
    )
    print("   완료!\n")

    # 3) 가상환경 Python으로 이 스크립트를 다시 실행
    os.execv(venv_python, [venv_python] + sys.argv)

_bootstrap()

# ──────────────────────────────────────────────
# 여기서부터는 가상환경 안에서 실행됩니다
# ──────────────────────────────────────────────
import re
import glob
import time
import base64
import shutil
import urllib.parse

import markdown
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# ─────────────────────────────────────────────
# 1. 마크다운 → HTML 변환 (이미지 base64 인라인)
# ─────────────────────────────────────────────
def convert_md_to_html_with_images(md_file_path):
    """마크다운 파일을 읽고, 이미지를 base64로 인라인 임베딩한 HTML을 반환합니다."""

    md_dir = os.path.dirname(md_file_path)

    with open(md_file_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    # 제목 추출: 파일 이름에서 .md 제거
    title = os.path.basename(md_file_path).replace(".md", "")

    # 이미지 참조를 base64 data URI로 치환
    def replace_image(match):
        alt_text = match.group(1)
        img_path_raw = match.group(2)
        # URL 인코딩된 경로 디코딩 (예: image%202.png → image 2.png)
        img_path_decoded = urllib.parse.unquote(img_path_raw)
        abs_img_path = os.path.join(md_dir, img_path_decoded)

        if os.path.exists(abs_img_path):
            ext = os.path.splitext(abs_img_path)[1].lower()
            mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp", ".svg": "image/svg+xml"}
            mime = mime_map.get(ext, "image/png")

            with open(abs_img_path, "rb") as img_f:
                b64 = base64.b64encode(img_f.read()).decode("utf-8")

            print(f"  ✓ 이미지 임베딩: {img_path_decoded}")
            return f'<img src="data:{mime};base64,{b64}" alt="{alt_text}" />'
        else:
            print(f"  ✗ 이미지 없음 (건너뜀): {img_path_decoded}")
            return match.group(0)  # 원본 유지

    # Markdown 이미지 구문: ![alt](path)
    md_text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', replace_image, md_text)

    # Markdown → HTML 변환
    html_body = markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "codehilite", "nl2br"],
    )

    return title, html_body


# ─────────────────────────────────────────────
# 2. 크롬 브라우저 실행 (프로필 자동 관리)
# ─────────────────────────────────────────────
def launch_chrome():
    """Selenium 크롬 드라이버를 실행합니다. 프로필 잠금 자동 정리 포함."""

    options = webdriver.ChromeOptions()
    options.add_experimental_option("detach", True)

    current_dir = os.path.dirname(os.path.abspath(__file__))
    profile_dir = os.path.join(current_dir, "chrome_profile")

    # 잠금 파일 자동 정리
    for lock_name in ("SingletonLock", "SingletonSocket", "SingletonCookie"):
        for lf in glob.glob(os.path.join(profile_dir, "**", lock_name), recursive=True):
            try:
                os.remove(lf)
            except:
                pass

    options.add_argument(f"--user-data-dir={profile_dir}")

    try:
        driver = webdriver.Chrome(options=options)
        return driver
    except Exception:
        # 프로필 손상 시 삭제 후 재시도
        print(">> 크롬 프로필 손상 감지 → 초기화 후 재시도합니다...")
        if os.path.exists(profile_dir):
            shutil.rmtree(profile_dir, ignore_errors=True)
        try:
            driver = webdriver.Chrome(options=options)
            return driver
        except Exception as e:
            print(f"\n[에러] 크롬을 시작할 수 없습니다: {e}")
            print("모든 크롬 창을 닫고 다시 시도해 주세요.")
            sys.exit(1)


# ─────────────────────────────────────────────
# 3. 티스토리 에디터에 JavaScript로 콘텐츠 주입
# ─────────────────────────────────────────────
def inject_content(driver, title, html_body):
    """JavaScript를 사용하여 TinyMCE 에디터에 제목과 본문을 직접 주입합니다."""

    wait = WebDriverWait(driver, 20)

    # 제목 입력 (React/Vue textarea 호환 — nativeInputValueSetter 사용)
    print(">> 제목 입력 중...")
    wait.until(EC.presence_of_element_located((By.ID, "post-title-inp")))

    # 제목을 base64로 안전하게 전달
    title_b64 = base64.b64encode(title.encode("utf-8")).decode("utf-8")
    driver.execute_script(f"""
        // UTF-8 base64 디코딩 함수
        function b64ToUtf8(b64) {{
            var binStr = atob(b64);
            var bytes = new Uint8Array(binStr.length);
            for (var i = 0; i < binStr.length; i++) {{
                bytes[i] = binStr.charCodeAt(i);
            }}
            return new TextDecoder('utf-8').decode(bytes);
        }}

        var titleEl = document.getElementById('post-title-inp');
        var titleText = b64ToUtf8('{title_b64}');

        // React 호환: native setter로 값 설정 후 이벤트 발생
        var nativeSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        nativeSetter.call(titleEl, titleText);
        titleEl.dispatchEvent(new Event('input', {{ bubbles: true }}));
        titleEl.dispatchEvent(new Event('change', {{ bubbles: true }}));
    """)
    print(f"   ✓ 제목: {title}")

    # 본문 입력 (TinyMCE API 직접 호출)
    print(">> 본문 입력 중...")

    # HTML 문자열을 JavaScript로 안전하게 전달하기 위해 base64 인코딩
    html_b64 = base64.b64encode(html_body.encode("utf-8")).decode("utf-8")

    # TinyMCE가 로드될 때까지 대기 후 setContent 호출 (UTF-8 디코딩 포함)
    success = driver.execute_script(f"""
        try {{
            // UTF-8 base64 디코딩 함수
            function b64ToUtf8(b64) {{
                var binStr = atob(b64);
                var bytes = new Uint8Array(binStr.length);
                for (var i = 0; i < binStr.length; i++) {{
                    bytes[i] = binStr.charCodeAt(i);
                }}
                return new TextDecoder('utf-8').decode(bytes);
            }}

            if (typeof tinymce !== 'undefined' && tinymce.activeEditor) {{
                var htmlContent = b64ToUtf8('{html_b64}');
                tinymce.activeEditor.setContent(htmlContent);
                return 'tinymce_ok';
            }}
            return 'tinymce_not_found';
        }} catch(e) {{
            return 'error: ' + e.message;
        }}
    """)

    if success == "tinymce_ok":
        print("   ✓ 본문 (TinyMCE에 직접 주입 완료)")
        return True
    else:
        print(f"   ⚠ TinyMCE 직접 주입 실패 ({success})")
        print("   → 대체 방법: HTML 모드로 전환하여 주입 시도...")

        # 대체: HTML 모드의 CodeMirror에 주입
        fallback_success = driver.execute_script(f"""
            try {{
                // HTML 에디터 컨테이너의 CodeMirror 찾기
                var htmlContainer = document.getElementById('html-editor-container');
                if (htmlContainer) {{
                    htmlContainer.style.display = 'block';
                }}
                var cmElements = document.querySelectorAll('.CodeMirror');
                for (var i = 0; i < cmElements.length; i++) {{
                    var cm = cmElements[i].CodeMirror;
                    if (cm) {{
                        var htmlContent = atob('{html_b64}');
                        cm.setValue(htmlContent);
                        return 'codemirror_ok';
                    }}
                }}
                return 'codemirror_not_found';
            }} catch(e) {{
                return 'error: ' + e.message;
            }}
        """)
        print(f"   결과: {fallback_success}")
        return fallback_success in ("codemirror_ok",)


# ─────────────────────────────────────────────
# 4. 메인 실행
# ─────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  티스토리 자동 업로더 v2  (JavaScript 주입 방식)")
    print("=" * 55)

    # 입력: 디렉토리 경로
    print(f"\n업로드할 폴더 경로를 입력하세요.")
    print("(UpNote에서 내보낸 폴더: .md 파일과 Files/ 이미지 폴더가 있는 경로)")
    target_dir = input("> ").strip()
    if not target_dir:
        print("[에러] 폴더 경로를 입력해 주세요.")
        return

    if not os.path.isdir(target_dir):
        print(f"[에러] 폴더를 찾을 수 없습니다: {target_dir}")
        return

    # .md 파일 찾기
    md_files = glob.glob(os.path.join(target_dir, "*.md"))
    if not md_files:
        print(f"[에러] 해당 폴더에 .md 파일이 없습니다: {target_dir}")
        return

    if len(md_files) == 1:
        md_file = md_files[0]
    else:
        print(f"\n{len(md_files)}개의 .md 파일이 있습니다:")
        for i, f in enumerate(md_files):
            print(f"  [{i+1}] {os.path.basename(f)}")
        choice = input("번호 선택: ").strip()
        md_file = md_files[int(choice) - 1]

    print(f"\n>> 대상 파일: {os.path.basename(md_file)}")

    # 블로그 ID 입력
    print("\n티스토리 블로그 ID를 입력하세요 (예: chsk)")
    blog_id = input("> ").strip()
    if not blog_id:
        print("[에러] 블로그 ID가 필요합니다.")
        return

    # Step 1: 마크다운 → HTML 변환
    print(f"\n{'─'*55}")
    print("[ Step 1/3 ] 마크다운 → HTML 변환 + 이미지 임베딩")
    print(f"{'─'*55}")
    title, html_body = convert_md_to_html_with_images(md_file)
    print(f"\n   변환 완료! (HTML 길이: {len(html_body):,}자)")

    # Step 2: 크롬 실행 & 에디터 열기
    print(f"\n{'─'*55}")
    print("[ Step 2/3 ] 크롬 브라우저 실행")
    print(f"{'─'*55}")
    driver = launch_chrome()

    write_url = f"https://{blog_id}.tistory.com/manage/post"
    print(f">> 글쓰기 페이지 이동: {write_url}")
    driver.get(write_url)
    time.sleep(3)

    print(f"\n{'='*55}")
    print("브라우저에서 글쓰기 에디터 화면이 보일 때까지 기다려 주세요!")
    print("")
    print("  • 로그인 화면이면 → 로그인 먼저!")
    print("  • 에디터(제목 + 본문)가 보이면 → 터미널에서 Enter!")
    print(f"{'='*55}\n")
    input("👉 에디터가 완전히 로딩되면 Enter를 누르세요... ")

    # Alert 처리
    try:
        while True:
            alert = driver.switch_to.alert
            print(f">> 알림창 처리: '{alert.text}'")
            alert.dismiss()
            time.sleep(0.5)
    except:
        pass

    # Step 3: 콘텐츠 주입
    print(f"\n{'─'*55}")
    print("[ Step 3/3 ] 제목 + 본문 자동 입력 (JavaScript 주입)")
    print(f"{'─'*55}")

    success = inject_content(driver, title, html_body)

    print(f"\n{'='*55}")
    if success:
        print("🎉 모든 작업이 완료되었습니다!")
        print("")
        print("  브라우저에서 내용을 확인하신 후")
        print("  우측 하단의 [완료] 버튼을 눌러 발행해 주세요!")
    else:
        print("⚠ 일부 자동 입력에 실패했습니다.")
        print("  브라우저에서 직접 확인 및 수정해 주세요.")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
