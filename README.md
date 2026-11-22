# smart-calc-kr · 스마트계산기

생활·금융·투자 실용 계산기 모음. 순수 HTML/CSS/JS 정적 사이트로, 빌드 도구가 필요 없습니다.

- 라이브: https://smart-calc-kr.pages.dev/ (Cloudflare Pages)
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

## 배포 (Cloudflare Pages)

빌드 도구가 없는 정적 사이트라 Cloudflare Pages에 저장소를 연결해 두면 `main` 브랜치에 푸시할 때마다 자동으로 다시 배포됩니다.

- 프로젝트: `smart-calc-kr` → https://smart-calc-kr.pages.dev/
- 설정: 프로덕션 브랜치 `main`, 프레임워크 미리 설정 `없음`, 빌드 명령 비움, 빌드 출력 디렉터리 `/`

```bash
git push origin main     # 푸시하면 30초 안에 자동 배포
```

HTTPS·전 세계 CDN·무료 트래픽 무제한이 기본이고, 나중에 개인 도메인을 붙일 때도 이 저장소 연결은 그대로 씁니다.

`deploy.sh`는 푸시와 배포 확인만 하는 보조 스크립트입니다. (예전 GitHub Pages(`gh-pages`) 배포는 더 이상 쓰지 않습니다.)

## 커스텀 도메인으로 바꿀 때

`smart-calc-kr.pages.dev` 문자열이 들어간 곳은 3종류입니다.

- 각 HTML의 `<link rel="canonical">`, `og:url`, JSON-LD의 `url`
- `sitemap.xml`의 `<loc>` 6개
- `robots.txt`의 `Sitemap:` 줄

커스텀 도메인은 Cloudflare Pages 프로젝트 → Custom domains에서 추가합니다(저장소에 `CNAME` 파일은 필요 없음).

```bash
grep -rn "smart-calc-kr.pages.dev" --include="*.html" --include="*.xml" --include="*.txt" .
```

메모: Cloudflare Pages는 `/salary.html` 요청을 `/salary`로 **308 리다이렉트**합니다(pretty URL 기본 동작). 그래서 canonical·사이트맵은 확장자 없는 주소를 씁니다.

## 검색엔진 등록 (2026-11-22)

루트의 아래 두 파일은 **구글 서치콘솔·네이버 서치어드바이저 소유확인이 끝난 파일**입니다. 지우거나 이름을 바꾸면 소유권 확인이 풀리므로 그대로 두세요.

| 파일 | 용도 |
| --- | --- |
| `google977142558e07955e.html` | 구글 서치콘솔 `https://smart-calc-kr.pages.dev/` (URL 접두어 속성, `dpdrntld2@gmail.com`) |
| `naver120c99234bfcbda06c8b128cb4b61e7d.html` | 네이버 서치어드바이저 `https://smart-calc-kr.pages.dev` (`life_hide@naver.com`) |
| `BingSiteAuth.xml` | Bing 웹마스터 도구 `https://smart-calc-kr.pages.dev/` (XML 파일 확인) |
| `2f174d526de74e46bef220ae582574e5.txt` | IndexNow API 키 파일 (Bing·api.indexnow.org 실시간 색인 제출용) |

- 세 곳 모두 `https://smart-calc-kr.pages.dev/sitemap.xml`을 제출한 상태입니다(Bing은 2026-11-22 Success, 6 URLs 발견).
- Cloudflare Pages가 `*.html` 요청을 확장자 없는 주소로 308 리다이렉트하지만, 확인 파일은 확장자 없는 주소에서도 같은 내용이 그대로 응답되어 두 엔진 모두 통과했습니다.
- 예전 GitHub Pages(`psh613.github.io/smart-calc-kr`)는 2026-11-22에 비활성화(Unpublish + Branch None)했습니다.
- 커스텀 도메인을 붙이면 두 엔진에 **새 주소를 사이트로 다시 추가**하고 소유확인을 새로 해야 합니다(속성별 확인이기 때문). `BingSiteAuth.xml`·IndexNow 키 파일도 새 도메인 기준으로 다시 발급·배치해야 합니다.

### 새 계산기를 배포한 뒤 색인 통보

```bash
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json; charset=utf-8' \
  --data '{"host":"smart-calc-kr.pages.dev","key":"2f174d526de74e46bef220ae582574e5","keyLocation":"https://smart-calc-kr.pages.dev/2f174d526de74e46bef220ae582574e5.txt","urlList":["https://smart-calc-kr.pages.dev/새주소"]}' \
  https://www.bing.com/indexnow   # 200 = 접수 (api.indexnow.org로 보내면 202)
```

- Bing 웹마스터 도구의 `URL Inspection` → `Request indexing`도 함께 쓰면 좋습니다(하루 100 URL 쿼터).
- `URL Submission` 메뉴는 신규 속성에서 "No pages found"로 비어 있어 IndexNow로 대체했습니다.

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
