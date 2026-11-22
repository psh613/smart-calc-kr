#!/bin/sh
# 저장소가 만들어진 뒤 GitHub에 푸시하고 GitHub Pages를 켜는 스크립트.
# 전제: Pickle의 GitHub 연결에 이 저장소의 Code 쓰기(Contents: Read and write) 권한이 있어야 한다.
set -e
cd "$(dirname "$0")"

if ! git remote get-url origin >/dev/null 2>&1; then
  git remote add origin https://github.com/psh613/smart-calc-kr.git
fi
git branch -M main

echo "▶ 푸시"
git push -u origin main

echo "▶ GitHub Pages 활성화"
gh api -X POST repos/psh613/smart-calc-kr/pages \
  -f build_type=legacy -f 'source[branch]=main' -f 'source[path]=/' >/dev/null 2>&1 \
  && echo "  Pages 생성 요청 완료" \
  || echo "  Pages API 실패(이미 활성화되었거나 권한 없음) — 저장소 Settings → Pages에서 main/(root) 선택"

echo "▶ 20초 뒤 응답 확인"
sleep 20
curl -s -o /dev/null -w "  HTTP %{http_code}  https://psh613.github.io/smart-calc-kr/\n" \
  https://psh613.github.io/smart-calc-kr/
