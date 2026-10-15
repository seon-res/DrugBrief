# DrugBrief — 의약품 허가·임상시험·규제정보 대시보드

FDA 의약품 허가 기록, ClinicalTrials.gov의 임상시험 등록정보, FDA / EMA 규제정보와 업로드받은 기존 규제 아카이브를 한 화면에서 검색하는 정적 웹사이트입니다. **코딩 초보자도 GitHub Pages에 배포할 수 있도록 별도 Node.js·AI API 키 없이 작동**하도록 제작했습니다.

## 🧭 세 가지 메뉴

1. **신규 의약품 허가·FDA 승인:** `openFDA Drugs@FDA`의 `NDA`/`BLA` 신청에 대한 original submission 승인(`ORIG` + `AP`) 기록. 보완 신청(`SUPPL`)과 제네릭 신청(`ANDA`)은 제외합니다. **이 목록은 FDA Novel Drug Approvals(NME/신규 생물학적 제제) 목록과 동일하지 않습니다.** 최근 240일간 확인한 결과 최대 250건을 보여 줍니다.
2. **임상시험 진행 현황:** ClinicalTrials.gov API v2에서 최근 변경된 중재시험 중 등록된 중재가 DRUG 또는 BIOLOGICAL인 자료 최대 200건. Phase, 상태, 개발사, 질환명, NCT 번호를 확인합니다. 이는 전체 임상시험 수가 아닌 최근 변경 기록의 표본입니다.
3. **제약 규제·가이드라인 변경:** FDA 연방관보 API, EMA 규제·과학 가이드라인 RSS, 기존 `pharma-regulation-site` ZIP에서 추출한 아카이브를 검색할 수 있습니다. **식약처 과거 자료의 자동 신규 수집은 이 버전에 포함되지 않습니다.** 식약처 항목은 사용자 제공 원본에 저장된 2026-10-15 스냅샷입니다. 공식 사이트를 통해 이후 개정 사항을 확인해 주세요.

FDA 승인 메뉴에는 승인서 확인 완료·승인서 영문 자동 발췌·승인 사유 확인 필요를 구분한 요약이 표시됩니다. PDF 발췌용 `pypdf`는 자동화가 선택적으로 설치하며, 설치 실패 시에도 자료 수집과 배포는 계속됩니다. 각 데이터 행에는 공식 출처 링크가 제공되며, 제목 클릭 → 상세 정보, 검색 필터링 및 CSV 다운로드를 이용할 수 있습니다.

## ✅ 처음 배포하기 (GitHub 웹사이트만으로 진행)

> 예시 저장소: `https://github.com/사용자아이디/DrugBrief`

1. 이 ZIP을 압축 해제합니다. 압축을 푼 폴더 **안에 있는 모든 내용물**을 업로드해야 합니다. (ZIP 자체만 업로드하면 작동하지 않습니다.)
2. GitHub → 본인의 `DrugBrief` 저장소 → **Code → Add file → Upload files**로 이동합니다. `index.html`, `assets`, `data`, `scripts`, `tests`, `.github`를 저장소 최상위에 업로드하고 커밋합니다.
3. `.github`가 Windows에서 숨겨지거나 업로드되지 않을 수 있습니다. **Code 탭에서 `.github/workflows/drugbrief-deploy.yml`이 존재하는지 확인**합니다. 없다면 GitHub의 Add file → Create new file에서 위 경로를 입력하고 ZIP 내부의 동일한 파일 내용을 붙여넣어 저장합니다.
4. 이전에 사용하던 `.github/workflows/update-and-deploy.yml` 등 **낡은 워크플로 파일은 삭제**해야 동일 저장소에서 배포 작업이 겹치지 않습니다. 오래된 `site/` 폴더는 이 프로젝트에서는 사용하지 않습니다.
5. **Settings → Pages → Build and deployment → Source: GitHub Actions**로 선택합니다.
6. 저장소 **Actions → DrugBrief 데이터 수집 및 배포 → Run workflow → Run workflow**를 누릅니다. `Run offline tests` → `Fetch official...` → `Prepare static publishing folder` → `Upload static site` → `Deploy GitHub Pages` 순서가 진행됩니다.
7. 성공하면 `https://사용자아이디.github.io/DrugBrief/`에서 열 수 있습니다. 저장소 이름이 다르거나 대소문자가 다르면 그 이름으로 URL을 변경하세요.

> **중요:** GitHub Actions에서 `Workflow permissions`가 Read-only로 강제된 저장소에서는 데이터 결과를 저장소에 다시 커밋하지 못할 수 있습니다. 이 경우 워크플로의 `Preserve latest successful data` 단계에 주황색 경고가 나오며, 배포 자체는 계속 진행합니다. `Settings → Actions → General → Workflow permissions`에서 Read and write permissions을 사용할 수 있는지 확인하세요. 설정이 정책에 의해 제한되면 데이터 수집은 매 실행마다 진행하지만 마지막 성공 기록의 보존은 제한될 수 있습니다.

## ⏰ 자동 갱신

`.github/workflows/drugbrief-deploy.yml`은 다음 경우 실행됩니다.
- `main` 혹은 `master` 브랜치에 신규 커밋이 생성될 때
- Actions에서 수동 실행할 때
- GitHub 예약 실행: **매일 한국시간 오전 10:27** (UTC 01:27). 실제 실행은 GitHub 서버 사정에 따라 지연·생략될 수 있습니다.

데이터 수집 파일: `scripts/update_data.py`. 실행 결과 JSON은 `data/`에 저장되며, 가능한 경우 `[skip ci]`를 사용한 별도 자동 커밋으로 마지막 성공 데이터를 보존합니다. 어떤 자료가 실패했는지 `data/metadata.json` 및 화면의 기관별 상태 뱃지에서 확인할 수 있습니다. 다른 자료의 수집·배포는 계속 진행합니다. **전 기관이 실패한 경우 비어 있는 항목은 자동 성공으로 위장하지 않습니다.**

### 오류가 발생한다면

| 단계 | 증상 | 확인 사항 |
|---|---|---|
| Actions 메뉴에 워크플로가 보이지 않음 | `.github/workflows/drugbrief-deploy.yml` 파일 누락 | 파일명이 정확한지, 기본 브랜치에 있는지 확인 |
| Run offline tests | 테스트 실패 | 업로드 파일이 빠지거나 스크립트가 수정되었는지 확인 |
| Fetch official… | API 요청 경고(WARN) | 일시적인 접근 실패·요청 제한 가능. 다른 기관은 계속 수집됨 |
| Configure/Deploy GitHub Pages | Pages 관련 오류 | `Settings → Pages → GitHub Actions`, 저장소 Actions 허용 여부 확인 |
| 페이지에서 JSON 읽기 실패 | 파일 경로 오류 | `data/` 폴더가 저장소 최상위인지 확인 |
| FDA/임상시험 결과 0건 | 첫 자동 수집 미실행 또는 기관 실패 | Actions에서 수동 실행 후 화면에서 기관별 상태 확인 |

GitHub Actions는 HTML·CSS·JS와 결과 JSON만 별도 `public/` 폴더에 넣어 배포하며, `.git` 등 소스 관리용 파일은 사이트에 게시하지 않습니다. GitHub Pages는 프런트엔드 정적 호스팅입니다. 데이터 수집은 방문자의 컴퓨터가 아니라 GitHub Actions의 Python으로 이루어지므로 API 키를 브라우저에 공개하지 않습니다.

## 🖥 로컬에서 미리보기

압축 해제한 폴더에서 다음 명령을 입력하세요.

```bash
python -m http.server 8000
```

브라우저에서 `http://localhost:8000`을 엽니다. 브라우저 파일 열기(`file://`)는 JSON 파일 읽기가 차단될 수 있습니다.

Python이 설치되어 있고 인터넷 연결이 허용되는 환경에서 수집을 테스트하려면:

```bash
python -m unittest discover -s tests -v
python scripts/update_data.py --run
```

외부 API가 실패하면 마지막에 성공한 저장 데이터가 유지되고, 실패 여부는 `data/metadata.json`에 기록됩니다.

## 파일 구조

```text
DrugBrief-upgraded/
├── .github/workflows/drugbrief-deploy.yml   # Actions: 수집 → 배포
├── index.html                               # 사이트 화면
├── assets/app.css                          # 원본의 파랑·남색 톤을 반영한 디자인
├── assets/app.js                           # 세 메뉴/검색/필터/상세/CSV
├── data/approvals.json                     # FDA 신규 원허가
├── data/trials.json                        # 임상시험 정보
├── data/regulations.json                   # 규제 통합 목록
├── data/regulations-archive.json           # 원본 ZIP 중 주요 규제 문서
├── data/regulations-history.json           # 원본 ZIP의 전체 규제 기록 6,944건
├── data/regulations-live-fda.json          # FDA 연방관보 업데이트
├── data/regulations-live-ema.json          # EMA 가이드라인 RSS
├── data/metadata.json                      # 수집 상태/성공 시각
├── scripts/update_data.py                  # 공식 API 수집 Python 코드
└── tests/test_pipeline.py                  # 오프라인 단위 테스트
```

## 데이터 정확도 및 범위

- **FDA 원허가**는 현재 기록상 신청 유형·승인 상태를 기준으로 합니다. 실제 제품의 최초 미국 시판, 신규 유효성분 또는 혁신 신약 여부와 구분해야 합니다. 제품명은 신청에 포함된 제품의 브랜드명이며, 임상적 효용을 뜻하지 않습니다.
- **임상시험**은 등록자가 입력한 표본 데이터입니다. LastUpdatePostDate는 ‘최근 변경 게시일’이지 ‘임상 시작일’ 또는 ‘신규 등록일’이 아닙니다. 최근 업데이트된 최대 200건만 표시하므로 시장 전체의 분포로 해석해서는 안 됩니다.
- **연방관보**는 FDA 명의의 문서 중 의약품 분야와 관련된 키워드가 포함된 자료를 수집합니다. 검색 용어에 따른 누락·과포함 가능성이 있고, 고시일과 시행일이 다를 수 있습니다.
- **EMA RSS**는 규제·과학 가이드라인 피드를 사용합니다. 기재된 게시일·설명에만 근거하며 전문 번역·AI 생성 요약 기능은 없습니다.
- **과거 아카이브**는 사용자가 제공한 `pharma-regulation-site-main.zip`의 정적 데이터에서 검색용 필드를 변환했습니다. 원본의 `api/details`와 빌드된 React JS는 새 프로젝트에 그대로 복제하지 않았습니다. 기존 정보와 해석은 각 공식 원문에서 다시 확인해야 합니다.
- FDA, ClinicalTrials.gov, EMA 및 Federal Register의 API 형식·접근 정책은 변경될 수 있으며, 이 ZIP의 데이터 수집 기능은 실제 운영 서버에서의 완전한 성공을 보증하지 않습니다.

**공식 정보 출처**
- [openFDA Drugs@FDA API](https://open.fda.gov/apis/drug/drugsfda/)
- [ClinicalTrials.gov API v2](https://clinicaltrials.gov/data-api/api)
- [Federal Register API](https://www.federalregister.gov/developers/documentation/api/v1)
- [EMA RSS 목록](https://www.ema.europa.eu/en/news-events/rss-feeds)
- [식품의약품안전처](https://www.mfds.go.kr/)

## 기존 프로젝트 안내

원본 업로드: [nawoonkim423/pharma-regulation-site](https://github.com/nawoonkim423/pharma-regulation-site). 원본 ZIP은 **정적 빌드 결과물**이며, 원 제작자의 수집·분석 원천코드는 포함되지 않습니다. 본 프로젝트는 업로드받은 규제 데이터의 검색용 재구성과 독립적으로 작성된 프런트엔드·수집 파이프라인을 사용합니다. 원본 프로젝트의 이름·출처를 표시해 주세요. 원본에 명시적 라이선스가 포함되어 있지 않으므로 외부 공개 전에는 원 제작자의 데이터·콘텐츠 재사용 허락과 이용 조건을 확인하는 것이 안전합니다.

## 📝 FDA NDA/BLA 승인 내용 요약 (2026-10-15 추가)

- **검토 완료:** `curated/approval-notes.json`에 담당자가 원허가 승인서를 실제로 확인하고 작성한 한국어 설명만 표시합니다. 신청번호 + 정확한 승인일이 모두 일치할 때만 해당 설명을 붙입니다. 예시로 **NDA220290, 2026-10-08, BREZTRI AEROSPHERE**를 FDA [원허가 승인서](https://www.accessdata.fda.gov/drugsatfda_docs/appletter/2026/220290Orig1s000ltr.pdf)에 근거해 수록했습니다.
- **영문 자동 발췌·검토 필요:** openFDA의 해당 ORIG submission에 연결된 approval letter PDF 중 첫 2쪽에서 `This NDA provides for...` 또는 `This BLA provides for...` 문장이 명확히 추출될 때만 원문 문장을 보여 줍니다. 이는 AI가 생성한 평가도 아니고 사람이 확인한 최종 판단도 아닙니다. 하루 최대 12건씩 자동 발췌를 시도합니다. PDF·API 문제로 발췌에 실패해도 배포는 계속됩니다.
- **확인 필요:** 승인서 문구를 파악하지 못한 항목에서는 FDA 제출 분류(`submission_class_code_description`)와 제품 제형만 보여 주고, 개별 승인 사유라고 단정하지 않습니다. FDA 승인서가 있는 경우 원문 링크를 제공합니다.
- NDA/BLA 원허가는 모두 신약 혁신성·신규 적응증 허가를 의미하지 않습니다. 같은 브랜드라도 새로운 NDA·첨가제·제형 허가일 수 있습니다.

직접 승인 내용을 더 추가할 때는 `curated/approval-notes.json`의 다른 객체와 같은 형식으로 `application`, `date`, `reason_ko`, `source_url`, `verified_at`을 넣으면 됩니다. 출처와 승인일이 없는 수동 요약은 시스템이 승인서 검토 완료로 표시하지 않습니다. 데이터 수집이 실행될 때마다 같은 신청번호와 날짜에 있는 요약이 자동 반영됩니다.

개별 승인서가 openFDA에 연결되지 않은 경우, 정확한 문서 URL을 확인한 뒤 수동 기록으로 추가하세요. GitHub에 코드를 다시 올린 후 Actions에서 수동 실행하거나 예약 실행을 기다리면 됩니다.
