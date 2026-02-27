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


# ── 카테고리 스캔 (Chirpy 2단계 계층 지원) ──

def scan_categories(blog_dir):
    """_posts/ 폴더의 기존 글에서 categories 값을 수집합니다.
    Chirpy 형식: categories: [대분류, 소분류]
    반환: {"Cloud": ["GCP"], "시스템": [], "달빛궁전": []}
    """
    posts_dir = os.path.join(blog_dir, "_posts")
    cat_tree = {}  # {대분류: set(소분류들)}

    if not os.path.isdir(posts_dir):
        return cat_tree

    for md_file in glob.glob(os.path.join(posts_dir, "*.md")):
        with open(md_file, "r", encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
        if match:
            try:
                fm = yaml.safe_load(match.group(1))
                if not fm:
                    continue
                cats = fm.get("categories", fm.get("category", None))
                if cats is None:
                    continue
                if isinstance(cats, str):
                    cats = [cats]
                if len(cats) >= 1:
                    main = cats[0]
                    if main not in cat_tree:
                        cat_tree[main] = set()
                    if len(cats) >= 2:
                        cat_tree[main].add(cats[1])
            except yaml.YAMLError:
                pass

    # set → sorted list
    return {k: sorted(list(v)) for k, v in sorted(cat_tree.items())}


def _pick_from_list(label, items, allow_new=True):
    """공통 번호 선택 UI"""
    for i, item in enumerate(items, 1):
        print(f"  {i}. {item}")
    if allow_new:
        new_option = len(items) + 1
        print(f"  {new_option}. (새로 입력)")
        max_num = new_option
    else:
        max_num = len(items)

    while True:
        choice = input(f"\n번호 입력 (1~{max_num}): ").strip()
        if not choice.isdigit():
            print("  숫자를 입력해 주세요.")
            continue
        num = int(choice)
        if 1 <= num <= len(items):
            selected = items[num - 1]
            print(f"  -> {selected}")
            return selected
        elif allow_new and num == new_option:
            new_val = input(f"  새 {label} 이름: ").strip()
            if new_val:
                return new_val
            print(f"  {label} 이름을 입력해 주세요.")
        else:
            print(f"  1~{max_num} 사이의 숫자를 입력해 주세요.")


def select_categories(cat_tree):
    """대분류 → 소분류 2단계 선택. [대분류] 또는 [대분류, 소분류] 리스트 반환."""

    # 1) 대분류 선택
    print("\n───────────────────────────────────────────────────────")
    print("  대분류를 선택하세요")
    print("───────────────────────────────────────────────────────")
    main_cats = list(cat_tree.keys())
    main = _pick_from_list("대분류", main_cats)

    # 2) 소분류 선택 (있으면)
    subs = cat_tree.get(main, [])
    print("\n───────────────────────────────────────────────────────")
    print(f"  소분류를 선택하세요 (대분류: {main})")
    print("───────────────────────────────────────────────────────")
    print(f"  0. 소분류 없이 [{main}]만 사용")
    if subs:
        for i, s in enumerate(subs, 1):
            print(f"  {i}. {s}")
    new_num = len(subs) + 1
    print(f"  {new_num}. (새 소분류 입력)")

    while True:
        choice = input(f"\n번호 입력 (0~{new_num}): ").strip()
        if not choice.isdigit():
            print("  숫자를 입력해 주세요.")
            continue
        num = int(choice)
        if num == 0:
            return [main]
        elif 1 <= num <= len(subs):
            sub = subs[num - 1]
            print(f"  -> {main} > {sub}")
            return [main, sub]
        elif num == new_num:
            new_sub = input("  새 소분류 이름: ").strip()
            if new_sub:
                print(f"  -> {main} > {new_sub}")
                return [main, new_sub]
            print("  소분류 이름을 입력해 주세요.")
        else:
            print(f"  0~{new_num} 사이의 숫자를 입력해 주세요.")


# ── 마크다운 변환 ──

def make_slug(title):
    """제목에서 파일명용 slug을 생성합니다."""
    slug = re.sub(r"[^\w\s가-힣-]", "", title)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug.lower()


def convert_upnote_to_jekyll(md_file_path, blog_dir, categories, tags=None, author="Seong Gi"):
    """UpNote 마크다운을 Chirpy 형식으로 변환하고 블로그 저장소에 복사합니다."""

    with open(md_file_path, "r", encoding="utf-8") as f:
        content = f.read()

    source_dir = os.path.dirname(md_file_path)
    files_dir = os.path.join(source_dir, "Files")

    # 제목 추출
    title_match = re.match(r"^#\s+(.+)$", content, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
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

    # 이미지 경로 변환
    def replace_image_path(match):
        alt = match.group(1)
        img_path = match.group(2)
        img_name = img_path
        if img_name.startswith("Files/"):
            img_name = img_name[6:]
        return f"![{alt}](/assets/images/posts/{slug}/{img_name})"

    content = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        replace_image_path,
        content
    )

    # Chirpy front matter 생성
    cat_str = json.dumps(categories, ensure_ascii=False)
    tag_str = json.dumps(tags, ensure_ascii=False) if tags else "[]"

    front_matter = f"""---
title: {title}
author: {author}
date: {today}
categories: {cat_str}
tags: {tag_str}
---

"""

    final_content = front_matter + content

    # _posts/ 에 저장
    posts_dir = os.path.join(blog_dir, "_posts")
    os.makedirs(posts_dir, exist_ok=True)
    dest_path = os.path.join(posts_dir, post_filename)

    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(final_content)

    cat_display = " > ".join(categories)
    return {
        "title": title,
        "filename": post_filename,
        "categories": cat_display,
        "tags": tags or [],
        "image_count": image_count,
        "dest_path": dest_path,
    }


# ── 블로그 경로 해석 (URL → 로컬 클론) ──

def _resolve_blog_dir(user_input):
    """
    사용자 입력이 로컬 경로면 그대로 반환,
    GitHub URL이면 홈 디렉토리에 자동 클론 후 경로 반환.
    """
    user_input = user_input.rstrip("/")

    # 이미 로컬 폴더가 존재하면 그대로 사용
    if os.path.isdir(user_input):
        return user_input

    # URL인지 확인
    git_url = None
    repo_name = None

    if "github.com/" in user_input:
        # https://github.com/SeongGi/seonggi.github.io 형태
        git_url = user_input
        if not git_url.endswith(".git"):
            git_url += ".git"
        repo_name = user_input.rstrip("/").split("/")[-1].replace(".git", "")
    elif ".github.io" in user_input and user_input.startswith("http"):
        # https://seonggi.github.io 형태 → GitHub 저장소 URL로 변환
        import urllib.parse
        parsed = urllib.parse.urlparse(user_input)
        username = parsed.hostname.split(".")[0]  # "seonggi"
        repo_name = parsed.hostname.split(".github.io")[0] + ".github.io"
        git_url = f"https://github.com/{username}/{repo_name}.git"

    if git_url:
        clone_dir = os.path.join(os.path.expanduser("~"), repo_name)

        if os.path.isdir(clone_dir):
            print(f"\n이미 클론된 저장소 발견: {clone_dir}")
            return clone_dir

        print(f"\n>> 블로그 저장소를 클론합니다...")
        print(f"   {git_url}")
        print(f"   → {clone_dir}")
        try:
            subprocess.check_call(["git", "clone", git_url, clone_dir])
            print("   완료!")
            return clone_dir
        except subprocess.CalledProcessError:
            print(f"\n[에러] git clone 실패. URL을 확인해 주세요: {git_url}")
            return None

    print(f"[에러] 폴더를 찾을 수 없습니다: {user_input}")
    return None


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

    config = load_config()

    # 블로그 저장소 경로
    saved_blog_dir = config.get("blog_dir", "")
    if saved_blog_dir and os.path.isdir(saved_blog_dir):
        print(f"\n현재 블로그 저장소: {saved_blog_dir}")
        print("(그대로 쓰려면 Enter, 변경하려면 새 경로 입력)")
        new_input = input("> ").strip()
        blog_dir = new_input if new_input else saved_blog_dir
    else:
        print("\nGitHub Pages 블로그 주소 또는 로컬 경로를 입력하세요.")
        print("  예시: https://github.com/유저이름/유저이름.github.io")
        print("  예시: https://유저이름.github.io")
        print("  예시: /Users/유저/유저이름.github.io")
        blog_dir = input("> ").strip()

    if not blog_dir:
        print("[에러] 경로를 입력해 주세요.")
        return

    # URL이 입력된 경우 → 자동 클론
    blog_dir = _resolve_blog_dir(blog_dir)
    if blog_dir is None:
        return

    # 최신 상태로 업데이트 (git pull)
    print(">> 블로그 저장소 최신 상태 동기화 중...")
    try:
        subprocess.check_call(
            ["git", "pull", "--rebase"], cwd=blog_dir,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        print("   완료!")
    except subprocess.CalledProcessError:
        print("   (pull 실패 - 오프라인이거나 충돌이 있을 수 있습니다. 계속 진행합니다.)")

    config["blog_dir"] = blog_dir
    save_config(config)

    # 카테고리 스캔 및 선택
    cat_tree = scan_categories(blog_dir)
    if not cat_tree:
        print("\n기존 카테고리가 없습니다. 새로 입력해 주세요.")
        main_cat = input("대분류 이름: ").strip()
        if not main_cat:
            print("[에러] 카테고리를 입력해 주세요.")
            return
        sub_cat = input("소분류 이름 (없으면 Enter): ").strip()
        categories = [main_cat, sub_cat] if sub_cat else [main_cat]
    else:
        categories = select_categories(cat_tree)

    # 태그 입력
    print("\n태그를 입력하세요 (쉼표로 구분, 없으면 Enter)")
    print("  예시: gcp, wif, security")
    tag_input = input("> ").strip()
    tags = [t.strip() for t in tag_input.split(",") if t.strip()] if tag_input else []

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

    result = convert_upnote_to_jekyll(md_file, blog_dir, categories, tags)

    print(f"\n  제목: {result['title']}")
    print(f"  파일: {result['filename']}")
    print(f"  카테고리: {result['categories']}")
    if result['tags']:
        print(f"  태그: {', '.join(result['tags'])}")
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
