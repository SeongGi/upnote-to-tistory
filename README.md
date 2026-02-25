# UpNote to Tistory Uploader

UpNote에서 작성한 마크다운 문서와 이미지를 티스토리(Tistory)에 원클릭으로 자동 업로드하는 도구입니다.

## 도입 배경 (Why?)
티스토리 Open API가 2024년 2월부로 종료되면서 외부 마크다운 에디터(UpNote, Obsidian 등)에서 작성한 글을 티스토리에 올리는 과정이 매우 번거로워졌습니다. 파일 업로드 API가 막히면서 이미지들을 일일이 수동으로 복사 및 붙여넣기 해야 하는 문제를 해결하고자 개발되었습니다.

## 주요 기능 (Features)
* 마크다운(.md) 완벽 지원: UpNote 등에서 내보낸 마크다운 파일을 HTML로 자동 변환합니다.
* 이미지 자동 임베드: 마크다운 파일과 함께 내보낸 로컬 이미지를 Base64 형태로 자동 변환 및 삽입합니다. 별도의 이미지 호스팅이나 API가 필요 없습니다.
* 에디터 자동화: Selenium을 활용해 티스토리 신형 에디터(TinyMCE)에 JavaScript로 직접 콘텐츠를 주입하여 타이핑이나 버튼 클릭 오류를 원천 차단했습니다.
* 크로스 플랫폼: Windows, Mac, Linux 환경에서 하나의 Python 스크립트로 구동됩니다.

## 필수 조건 (Prerequisites)
* Python 3.10 이상
* Google Chrome 브라우저
* UpNote (또는 로컬 이미지 폴더를 함께 내보낼 수 있는 마크다운 에디터)

## 설치 (Installation)

1. 저장소 클론 또는 다운로드
```bash
git clone https://github.com/SeongGi/upnote-to-tistory.git
cd upnote-to-tistory
```

2. 필수 패키지 설치
```bash
pip install -r requirements.txt
```

## 사용법 (Usage)

1. UpNote에서 작성한 글을 마크다운으로 내보내기 합니다. 문서 1개 내보내기 시 폴더가 생성되며, 그 안에 .md 파일과 Files/ 보조 폴더가 생깁니다.
2. 터미널(명령 프롬프트)에서 아래 명령어를 실행합니다.
```bash
python tistory_uploader.py
```
3. 터미널 스크립트 안내에 따라 UpNote에서 내보낸 폴더 경로와 티스토리 영문 ID를 입력합니다.
4. 크롬 창이 열리면 티스토리에 로그인을 진행합니다. 최초 1회만 진행하며, 이후엔 프로필 세션이 유지되어 창이 열리자마자 자동 로그인됩니다.
5. 티스토리 글쓰기 에디터 화면이 완전히 로딩되면 터미널 창에서 Enter 키를 누릅니다.
6. 자동으로 제목과 본문(이미지가 포함된 HTML)이 에디터에 주입됩니다.
7. 브라우저 우측 하단의 완료 버튼을 눌러 최종 발행을 마칩니다.

## 동작 원리 (How it works?)
과거 UI 버튼을 일일이 클릭하던 매크로 방식은 에디터 구조가 바뀔 때마다 고장나고 속도에 한계가 있었습니다. 
본 도구는 마크다운을 스크립트 내부에서 HTML 파일로 렌더링(로컬 이미지를 base64 문자로 치환) 한 뒤, Selenium 라이브러리를 통해 티스토리 에디터가 내부적으로 사용하는 JS API(React, TinyMCE)에 변환된 HTML 데이터를 직접 꽂아넣는 방식을 채택하여 우수한 안정성과 속도를 보여줍니다.

## 파일 구조
```text
upnote-to-tistory/
├── tistory_uploader.py   # 메인 자동화 스크립트
├── requirements.txt      # Python 패키지 의존성 목록
└── README.md             # 안내 문서
```

## 기여 (Contributing)
버그 리포트, 기능 제안, 풀 리퀘스트는 언제나 환영합니다.

## 라이선스 (License)
이 프로젝트는 MIT 라이선스에 따라 배포됩니다. 자유롭게 사용하고 수정하세요.
