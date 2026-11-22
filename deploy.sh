#!/bin/sh
# main 브랜치에 푸시하면 Cloudflare Pages(smart-calc-kr)가 자동으로 빌드·배포한다.
# 이 스크립트는 푸시 후 배포가 실제로 반영됐는지 확인하는 용도.
set -e
cd "$(dirname "$0")"

BASE="https://smart-calc-kr.pages.dev"

echo "▶ 테스트"
python3 tests/test_pages.py
python3 tests/test_calc.py >/dev/null && echo "  계산 로직 테스트 통과"

echo "▶ 푸시 (main → Cloudflare Pages 자동 배포)"
git push origin main

echo "▶ 30초 뒤 응답 확인"
sleep 30
for p in "" salary crypto compound sitemap.xml robots.txt; do
  printf "  %-14s " "/$p"
  curl -s -o /dev/null -w "HTTP %{http_code}\n" "$BASE/$p"
done
