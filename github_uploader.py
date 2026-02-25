"""
GitHub Pages 블로그 자동 업로더
================================
UpNote에서 내보낸 마크다운(.md) 파일과 이미지들을
Jekyll 기반 GitHub Pages 블로그에 자동으로 업로드하는 스크립트입니다.

Selenium이나 Chrome 없이 순수 git 명령어로 동작합니다.
처음 실행 시 자동으로 가상환경(.venv) 생성 및 패키지 설치가 진행됩니다.
"""

# ──────────────────────────────────────────────
# 자동 환경 설정 (venv 생성 + 패키지 설치)
# ──────────────────────────────────────────────
import sys
import os
import subprocess

REQUIRED_PACKAGES = ["PyYAML"]

def _bootstrap():
    """가상환경이 아니면 자동으로 생성하고 패키지를 설치한 뒤 재실행합니다."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(script_dir, ".venv")

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

    if not os.path.exists(venv_python):
        print("\n>> 가상환경 생성 중... (.venv)")
        subprocess.check_call([sys.executable, "-m", "venv", venv_dir])
        print("   완료!")

    print(">> 필수 패키지 설치 중...")
    subprocess.check_call(
        [venv_python, "-m", "pip", "install", "--upgrade", "pip", "-q"],
    )
    subprocess.check_call(
        [venv_python, "-m", "pip", "install"] + REQUIRED_PACKAGES + ["-q"],
    )
    print("   완료!\n")

    os.execv(venv_python, [venv_python] + sys.argv)

_bootstrap()

# ──────────────────────────────────────────────
# 여기서부터는 가상환경 안에서 실행됩니다
# ──────────────────────────────────────────────
import re
import glob
import json
import shutil
import datetime
import yaml


# ── 설정 파일 관리 ──

CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".github_uploader.json")

def load_config():
    """저장된 설정을 불러옵니다."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(config):
    """설정을 파일에 저장합니다."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ── 카테고리 스캔 ──

def scan_categories(blog_dir):
    """_posts/ 폴더의 기존 글에서 category 값을 수집합니다."""
    posts_dir = os.path.join(blog_dir, "_posts")
    categories = set()

    if not os.path.isdir(posts_dir):
        return sorted(list(categories))

    for md_file in glob.glob(os.path.join(posts_dir, "*.md")):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        # front matter 파싱 (--- ... --- 사이)
        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if match:
            try:
                fm = yaml.safe_load(match.group(1))
                if fm and "category" in fm:
                    categories.add(str(fm["category"]))
            except yaml.YAMLError:
                pass

    return sorted(list(categories))


def select_category(categories):
    """카테고리 목록을 번호로 보여주고 사용자에게 선택받습니다."""
    print("\n───────────────────────────────────────────────────────")
    print("  카테고리를 선택하세요")
    print("───────────────────────────────────────────────────────")

    for i, cat in enumerate(categories, 1):
        print(f"  {i}. {cat}")
    new_option = len(categories) + 1
    print(f"  {new_option}. (새 카테고리 직접 입력)")

    while True:
        choice = input(f"\n번호 입력 (1~{new_option}): ").strip()
        if not choice.isdigit():
            print("  숫자를 입력해 주세요.")
            continue
        num = int(choice)
        if 1 <= num <= len(categories):
            selected = categories[num - 1]
            print(f"  -> {selected}")
            return selected
        elif num == new_option:
            new_cat = input("  새 카테고리 이름: ").strip()
            if new_cat:
                return new_cat
            print("  카테고리 이름을 입력해 주세요.")
        else:
            print(f"  1~{new_option} 사이의 숫자를 입력해 주세요.")


# ── 마크다운 변환 ──

def make_slug(title):
    """제목에서 파일명용 slug을 생성합니다."""
    # 특수문자 제거, 공백을 하이픈으로
    slug = re.sub(r"[^\w\s가-힣-]", "", title)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug.lower()


def convert_upnote_to_jekyll(md_file_path, blog_dir, category, author="Seong Gi"):
    """UpNote 마크다운을 Jekyll 형식으로 변환하고 블로그 저장소에 복사합니다."""

    with open(md_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 원본 폴더 (이미지가 들어있는 Files/ 폴더의 부모)
    source_dir = os.path.dirname(md_file_path)
    files_dir = os.path.join(source_dir, "Files")

    # 제목 추출 (첫 번째 # 헤더 또는 파일명)
    title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        # 본문에서 제목 줄 제거 (Jekyll은 front matter의 title을 사용)
        content = content[:title_match.start()] + content[title_match.end():]
        content = content.lstrip("\n")
    else:
        title = os.path.splitext(os.path.basename(md_file_path))[0]

    slug = make_slug(title)
    today = datetime.date.today().strftime("%Y-%m-%d")
    post_filename = f"{today}-{slug}.md"

    # 이미지 처리
    image_dest_dir = os.path.join(blog_dir, "assets", "images", "posts", slug)
    image_count = 0

    if os.path.isdir(files_dir):
        os.makedirs(image_dest_dir, exist_ok=True)

        for img_file in os.listdir(files_dir):
            src_path = os.path.join(files_dir, img_file)
            if os.path.isfile(src_path):
                dst_path = os.path.join(image_dest_dir, img_file)
                shutil.copy2(src_path, dst_path)
                image_count += 1
                print(f"  이미지 복사: {img_file}")

    # 마크다운 내 이미지 경로 변환
    # UpNote 형식: ![](Files/image.png) 또는 ![alt](Files/image 2.png)
    def replace_image_path(match):
        alt = match.group(1)
        img_path = match.group(2)
        # Files/ 접두사 제거
        img_name = img_path
        if img_name.startswith("Files/"):
            img_name = img_name[6:]
        return f"![{alt}](/assets/images/posts/{slug}/{img_name})"

    content = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        replace_image_path,
        content
    )

    # front matter 생성
    front_matter = f"""---
title: {title}
author: {author}
date: {today}
category: {category}
layout: post
---

"""

    final_content = front_matter + content

    # _posts/ 에 저장
    posts_dir = os.path.join(blog_dir, "_posts")
    os.makedirs(posts_dir, exist_ok=True)
    dest_path = os.path.join(posts_dir, post_filename)

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    return {
        "title": title,
        "filename": post_filename,
        "category": category,
        "image_count": image_count,
        "dest_path": dest_path,
    }


# ── Git 자동화 ──

def git_push(blog_dir, commit_message):
    """변경사항을 커밋하고 push 합니다."""
    try:
        subprocess.check_call(["git", "add", "-A"], cwd=blog_dir)
        subprocess.check_call(["git", "commit", "-m", commit_message], cwd=blog_dir)
        subprocess.check_call(["git", "push"], cwd=blog_dir)
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n[에러] git 명령 실패: {e}")
        return False


# ── 메인 ──

def main():
    print()
    print("=" * 55)
    print("  GitHub Pages 블로그 자동 업로더")
    print("=" * 55)

    # 설정 불러오기
    config = load_config()

    # 블로그 저장소 경로
    saved_blog_dir = config.get("blog_dir", "")
    if saved_blog_dir and os.path.isdir(saved_blog_dir):
        print(f"\n저장된 블로그 경로: {saved_blog_dir}")
        use_saved = input("이 경로를 사용하시겠습니까? (Y/n): ").strip().lower()
        if use_saved in ("", "y", "yes"):
            blog_dir = saved_blog_dir
        else:
            blog_dir = input("블로그 저장소 경로를 입력하세요: ").strip()
    else:
        print("\n블로그 저장소(seonggi.github.io)의 로컬 경로를 입력하세요.")
        print("(git clone 한 폴더 경로)")
        blog_dir = input("> ").strip()

    if not blog_dir or not os.path.isdir(blog_dir):
        print(f"[에러] 폴더를 찾을 수 없습니다: {blog_dir}")
        return

    # 블로그 경로 저장
    config["blog_dir"] = blog_dir
    save_config(config)

    # 카테고리 스캔 및 선택
    categories = scan_categories(blog_dir)
    if not categories:
        print("\n기존 카테고리가 없습니다. 새로 입력해 주세요.")
        category = input("카테고리 이름: ").strip()
        if not category:
            print("[에러] 카테고리를 입력해 주세요.")
            return
    else:
        category = select_category(categories)

    # UpNote 폴더 경로
    print("\nUpNote에서 내보낸 폴더 경로를 입력하세요.")
    print("(.md 파일과 Files/ 이미지 폴더가 있는 경로)")
    target_dir = input("> ").strip()

    if not target_dir or not os.path.isdir(target_dir):
        print(f"[에러] 폴더를 찾을 수 없습니다: {target_dir}")
        return

    # .md 파일 찾기
    md_files = glob.glob(os.path.join(target_dir, "*.md"))
    if not md_files:
        print(f"[에러] 해당 폴더에 .md 파일이 없습니다: {target_dir}")
        return

    md_file = md_files[0]
    print(f"\n대상 파일: {os.path.basename(md_file)}")

    # 변환 및 복사
    print("\n───────────────────────────────────────────────────────")
    print("  마크다운 변환 + 이미지 복사")
    print("───────────────────────────────────────────────────────")

    result = convert_upnote_to_jekyll(md_file, blog_dir, category)

    print(f"\n  제목: {result['title']}")
    print(f"  파일: {result['filename']}")
    print(f"  카테고리: {result['category']}")
    print(f"  이미지: {result['image_count']}개 복사됨")

    # git push
    print("\n───────────────────────────────────────────────────────")
    print("  Git Push")
    print("───────────────────────────────────────────────────────")

    commit_msg = f"새 글 추가: {result['title']}"
    print(f"  커밋 메시지: {commit_msg}")

    confirm = input("\n  Push 하시겠습니까? (Y/n): ").strip().lower()
    if confirm in ("", "y", "yes"):
        success = git_push(blog_dir, commit_msg)
        if success:
            print("\n" + "=" * 55)
            print("  완료! 1~2분 후 사이트에 반영됩니다.")
            print("=" * 55)
        else:
            print("\n  Push에 실패했습니다. 수동으로 진행해 주세요:")
            print(f"    cd {blog_dir}")
            print(f'    git add -A && git commit -m "{commit_msg}" && git push')
    else:
        print("\n  Push를 취소했습니다. 수동으로 진행하려면:")
        print(f"    cd {blog_dir}")
        print(f'    git add -A && git commit -m "{commit_msg}" && git push')


if __name__ == "__main__":
    main()
