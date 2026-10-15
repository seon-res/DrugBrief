# Pharma Insight: FDA 승인 + 신약 임상시험 대시보드

한국어 인터페이스를 제공하는 **정적 웹사이트 + 매일 자동 수집** 시작 프로젝트입니다.

## 파일 구조

```text
pharma-insight-starter/
├── .github/workflows/update-and-deploy.yml  # 예약 실행 + GitHub Pages 배포
├── scripts/fetch_data.py                     # FDA / ClinicalTrials.gov 자동 수집
├── site/
│   ├── index.html                            # 웹 페이지
│   ├── styles.css                            # 디자인
│   ├── app.js                                # 검색, 단계별 필터, 카드 생성
│   ├── data.json                             # 초기에는 명확히 표시된 가상 예시 데이터
│   └── .nojekyll                             # 정적 사이트 호환성
├── tests/test_fetch_data.py                  # 파싱 단위 테스트
└── README.md
```

## 가장 쉬운 배포 (브라우저만 사용)

1. https://github.com/new 에서 이름이 `pharma-insight`인 **Public** 저장소 생성. 기본 브랜치 `main`.
2. 이 ZIP을 컴퓨터에서 **압축 해제**합니다.
3. 저장소의 **Add file → Upload files**에서 `README.md`, `scripts` 폴더, `site` 폴더의 파일을 업로드합니다. 단, GitHub 웹 업로드에서는 **숨김 폴더 `.github`가 누락되기 쉽습니다.** 다음 4번처럼 별도 생성하는 것이 확실합니다.
4. 저장소에서 **Add file → Create new file** 클릭 후 파일 이름에 `.github/workflows/update-and-deploy.yml`을 입력하고, ZIP에 들어있는 동일 이름 파일의 전체 내용을 붙여넣은 후 **Commit changes**합니다.
5. 저장소 **Settings → Pages → Build and deployment → Source: GitHub Actions**로 설정합니다. (중요: 이 프로젝트는 `Deploy from a branch` 방식이 아니라 `GitHub Actions` 방식입니다.)
6. 저장소 **Actions → Update data and deploy site → Run workflow → Run workflow**를 눌러 수동 실행합니다. `main` 브랜치 기준입니다.
7. Actions 실행에 성공하면 사이트는 `https://YOUR_GITHUB_ID.github.io/pharma-insight/`로 공개됩니다.
8. 매일 **한국시간 10:27경** 예약 실행됩니다. GitHub 사정으로 실행이 지연되거나 건너뛰어질 수 있습니다.

### 숨김 파일 업로드 주의

가능하다면 VS Code 또는 Git 명령을 통해 **ZIP의 전체 폴더 구조를 그대로 저장소에 업로드**하세요. 특히 `.github/workflows/update-and-deploy.yml`이 정확히 있어야 자동화가 동작합니다. 브라우저의 업로드 기능이나 운영체제 설정에 따라 숨김 폴더가 보이지 않을 수 있습니다.

## 컴퓨터에서 미리보기

프로젝트 루트 폴더에서:

```bash
python -m http.server 8000 --directory site
```

그다음 브라우저에서 `http://localhost:8000`을 방문합니다. 초기 data.json은 **가상 샘플 데이터**이며, 상단에 노란색 안내가 나타납니다. HTML 파일을 그냥 더블클릭하지 마세요. `fetch()` 때문에 로컬 서버가 필요합니다.

## 직접 실데이터 업데이트

```bash
python scripts/fetch_data.py
```

Python 3.10+ 필요. API 키 및 별도 Python 패키지 설치는 필요하지 않습니다. 인터넷과 양쪽 공식 API가 정상일 때 업데이트됩니다. 하나만 실패하면 부분 갱신 경고, 둘 다 실패하면 프로그램이 종료되어 기존 배포를 그대로 유지합니다.

## 수집 범위와 한계

- **FDA:** 최근 365일 사이의 Drugs@FDA `ORIG` + `AP` 제출건에서 `NDA`/`BLA`만 필터. **최대 6페이지(페이지당 100개 신청서)**를 조회하고 승인일 기준 상위 **40건** 표시. 신청서 단위 API에는 여러 제출 기록이 포함되기 때문에, 코드에서 각 제출 기록의 유형·상태·날짜를 다시 검사합니다. 이것은 **모든 FDA 혁신 신약 승인 목록이 아닙니다**. API의 검색·정렬 방식 때문에 개별 승인 누락 가능성이 있습니다. 수집한 `date`는 원승인 날짜입니다.
- **ClinicalTrials.gov:** 최근에 등록정보가 업데이트된 산업체 주도, 중재시험 중 `DRUG`/`BIOLOGICAL` 연구, Phase 1–3 포함 연구. **최신 업데이트 300개를 조회하여 조건에 맞는 최대 80건**만 표시합니다. 전 세계 모든 신약 임상시험 또는 모든 신규 등록의 완전한 목록이 아닙니다. `date`는 등록정보의 게시 업데이트 날짜이지 최초 등록일, 개시일, 결과 발표일이 아닙니다.
- 사이트 통계는 **표시된 레코드 수**만 셉니다.
- FDA 승인 데이터는 최신 시점이 원본 데이터 반영 시점보다 지연될 수 있습니다.
- 표기된 회사는 ClinicalTrials.gov **lead sponsor** 또는 Drugs@FDA **application sponsor**입니다. 실제 개발사·라이선스 보유사와 다를 수 있습니다.
- 모든 표시 텍스트는 외부 API를 받으므로, HTML 문자열 삽입 대신 브라우저 `textContent`로 안전하게 표시합니다.
- 개발·투자·임상·의료 의사결정 전에는 반드시 제공된 FDA 또는 ClinicalTrials.gov 원문을 재확인해야 합니다.

## 흔한 오류

- **Actions에 워크플로가 안 보임**: `.github/workflows/update-and-deploy.yml`의 경로, 파일명 및 `main` 브랜치를 확인합니다.
- **Pages 404**: Settings → Pages의 Source가 `GitHub Actions`인지, 배포 workflow가 성공했는지 확인합니다.
- **API 실패**: GitHub Actions의 실행 로그에서 데이터 수집 단계의 에러를 확인하고 나중에 `Run workflow`로 재시도합니다.
- **화면이 예시 데이터로 남음**: Actions 성공 전 상태일 수 있습니다. `site/data.json`이 동적으로 갱신된 웹사이트에서 `mode: live`인지 확인해 보세요.
- **60일 후 자동 업데이트 중단**: 공개 저장소에서 활동이 없는 경우 GitHub가 예약 워크플로를 자동 비활성화할 수 있습니다. Actions에서 다시 활성화할 수 있습니다.

## 공식 참고 링크

- https://open.fda.gov/apis/drug/drugsfda/
- https://clinicaltrials.gov/data-api/api
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows

## 사용료

사이트 자체는 일반적인 공개 GitHub Pages 및 공개 저장소의 GitHub Actions 무료 사용 범위에서 운영할 수 있습니다(사용량·요금 정책은 GitHub에서 확인). 이 예제는 유료 AI API를 호출하지 않습니다. 예시 데이터를 AI가 요약한 것처럼 표시하지 않습니다.
