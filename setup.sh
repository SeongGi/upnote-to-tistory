#!/bin/bash
echo "============================================"
echo "  티스토리 자동 업로더 - 설치 (Mac/Linux)"
echo "============================================"
echo ""

# Python 설치 확인
if ! command -v python3 &> /dev/null; then
    echo "[에러] Python3이 설치되어 있지 않습니다."
    echo "Mac: brew install python3"
    echo "Linux: sudo apt install python3 python3-venv"
    exit 1
fi

echo "[1/2] 가상환경 생성 중..."
python3 -m venv .venv

echo "[2/2] 필요 패키지 설치 중..."
source .venv/bin/activate
pip install -r requirements.txt -q

echo ""
echo "============================================"
echo "  설치 완료!"
echo "  실행하려면: ./run.sh"
echo "============================================"
