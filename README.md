# smart-calc-kr · 스마트계산기

생활·금융·투자 실용 계산기 모음. 순수 HTML/CSS/JS 정적 사이트로, 빌드 도구가 필요 없습니다.

- 라이브(예정): https://psh613.github.io/smart-calc-kr/
- 저장소: https://github.com/psh613/smart-calc-kr

## 계산기

| 페이지 | 내용 |
|---|---|
| `index.html` | 계산기 허브 (카드 그리드 + 사용 팁) |
| `salary.html` | 2026 연봉 실수령액 (4대보험 4종 · **근로소득 간이세액표 원천징수** · 지방소득세, 연말정산 예상, 연봉별 비교, FAQ) |
| `crypto.html` | 코인 물타기 평단가 + 선물 롱/숏 레버리지별 예상 청산가 (원·달러 병기, 환율 직접 입력) |
| `compound.html` | 적립식 투자(DCA)·복리 (연도별 표) |
| `about.html` / `privacy.html` | 사이트 소개 / 개인정보처리방침 (광고 심사 대비) |
| `sitemap.xml` / `robots.txt` | 검색엔진 등록용 |

## 파일 구조

```
smart-calc-kr/
├── index.html  salary.html  crypto.html  compound.html  about.html  privacy.html
├── assets/
│   ├── style.css              공용 디자인 (모바일 우선)
│   ├── calc-core.js           계산 로직 (DOM 없음 · 테스트 대상)
│   ├── withholding-table.js   2026년 근로소득 간이세액표 (소득세법 시행령 별표2, 자동 생성)
│   ├── ui.js                  숫자 포맷·환율·입력 바인딩
│   └── salary.js  crypto.js  compound.js   페이지별 렌더링
├── tools/build_withholding_table.py   별표2 PDF → withholding-table.js 변환
├── tests/test_calc.py          계산 로직 검증
├── tests/test_pages.py         파일·id·메타·사이트맵 정적 점검
├── favicon.svg  sitemap.xml  robots.txt  .nojekyll
└── README.md
```

## 왜 소득세가 "간이세액표"인가

급여명세서의 소득세는 연말정산 계산값이 아니라 **근로소득 간이세액표(소득세법 시행령 별표 2)** 값을 그대로 뗀 것입니다. 연간 공제를 12로 나누는 방식은 명세서와 최대 20~30% 어긋나므로, 이 사이트는 별표 2의 **646개 구간 × 공제대상가족 1~11명 표를 그대로 내장**(`assets/withholding-table.js`, 약 38KB)해 급여명세서와 같은 값을 보여 줍니다. 1,000만원 초과 구간은 별표 2가 정한 계산식을 씁니다. 연말정산 예상액은 별도로 `computeAnnualTax()`가 계산합니다.

## 로컬에서 보기

```bash
cd smart-calc-kr
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000
```

## GitHub에 올리고 배포하기

1. GitHub에서 `smart-calc-kr` 이름의 **Public** 저장소를 만든다(README 추가하지 않음).
2. 이 폴더에서:

```bash
git remote add origin https://github.com/psh613/smart-calc-kr.git
git branch -M main
git push -u origin main
```

3. 저장소 → Settings → Pages → Source: `Deploy from a branch`, Branch: `main` / `/ (root)` → Save.
4. 1~2분 뒤 https://psh613.github.io/smart-calc-kr/ 가 열린다.

## 커스텀 도메인으로 바꿀 때

`psh613.github.io/smart-calc-kr` 문자열이 들어간 곳은 4종류입니다.

- 각 HTML의 `<link rel="canonical">`, `og:url`, JSON-LD의 `url`
- `sitemap.xml`의 `<loc>` 6개
- `robots.txt`의 `Sitemap:` 줄
- GitHub Pages 설정의 Custom domain (저장소에 `CNAME` 파일도 자동 생성됨)

```bash
grep -rn "psh613.github.io" --include="*.html" --include="*.xml" --include="*.txt" .
```

## 요율 갱신 위치

2026년 제도 값은 `assets/calc-core.js`의 `R2026` 객체 한 곳에 모여 있습니다. 국민연금·건강보험·장기요양 요율, 기준소득월액 상·하한, 식대 비과세 한도, 기본공제 단가, 자녀세액공제 금액이 여기 있습니다. 소득세율 구간은 같은 파일의 `BRACKETS`, 근로소득공제는 `wageDeduction()` 함수에 있습니다.

간이세액표는 매년 3월 1일 원천징수분부터 새 별표가 적용됩니다. 개정되면:

```bash
curl -sL -o table.pdf "https://www.law.go.kr/LSW/flDownload.do?flSeq=<새 일련번호>"
python3 tools/build_withholding_table.py table.pdf   # assets/withholding-table.js 재생성
python3 tests/test_calc.py                           # 공개 값과 다시 대조
```

## 검증

```bash
python3 tests/test_calc.py    # 계산 로직 553건 (표 공개값·실수령 사례·경계값)
python3 tests/test_pages.py   # 정적 점검 197건 (파일·id 결선·메타·사이트맵)
```

`test_calc.py`는 `quickjs`(pip)로 실제 JS를 실행해 대조합니다. 검증 항목에 포함된 것:

- 간이세액표 8개 급여 × 4개 가족 수 = 32개 값이 국세청 고시 표와 일치
- 월 400만원·1명 실수령 3,395,760원, 월 400만원·4명(자녀 2명) 3,560,890원 등 공개 사례와 일치
- 국민연금 상·하한(41만/659만), 식대 비과세 한도, 1,000만원 초과 구간 연속성
- 물타기 평단가·선물 청산가·복리 10년, 0으로 나누기·음수·범위 초과 방어

## 참고

계산 결과는 공개된 법령·요율을 바탕으로 한 추정치입니다. 세금·보험료는 개인 상황(기준소득월액 신고액, 자녀·의료비·카드 공제 등)에 따라 달라지고, 청산가는 거래소 정책에 따라 실시간으로 바뀝니다.
