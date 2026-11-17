# VideoBatchConverter · Visual Identity 3.0

**영상은 선명하게, 보관은 가볍게.**

여러 개의 영상 프레임이 차례로 겹쳐 하나의 결과를 만드는 모습을 심볼로 사용한다. 라벤더 → 민트 → 블루의 세 프레임은 파일 수집, 설정, 변환의 흐름을 나타내며 흰색 재생 표식으로 동영상 도구임을 드러낸다.

## 기본 자산

| 용도 | 파일 |
| --- | --- |
| 기본 심볼, 앱 내부 | `mark.svg` |
| 단색 인쇄·스탬프 | `mark-mono.svg` |
| 가로 로고와 슬로건 | `wordmark.svg`, `wordmark.png` |
| Windows 앱·배포 아이콘 | `app-icon.ico` |
| 웹·문서·바로가기 | `app-icon-{16,24,32,48,64,128,256,512,1024}.png` |
| 전체 CI 미리보기 | `brand-board.svg`, `brand-board.png` |
| GitHub 소셜 미리보기 | `../social/social-card.svg`, `../social/social-card.png` |

## 색상

| 이름 | HEX | 역할 |
| --- | --- | --- |
| Action blue | `#4263EB` | 주요 실행, 활성 프리셋, 진행률 |
| Ink | `#202B45` | 제목과 본문 |
| Muted | `#62708A` | 보조 설명 |
| Canvas | `#F5F7FC` | 기본 배경 |
| Surface | `#FFFFFF` | 카드·입력 영역 |
| Mint / Teal | `#DDF5EE` / `#187967` | 준비·완료·보관 |
| Lavender / Purple | `#EEE8FF` / `#7653B5` | 기기·AV1 |
| Peach / Orange | `#FFF0E2` / `#9F541D` | 업로드·콘텐츠 |
| Error | `#B3424F` | 오류·중지 |

파스텔 색상은 면과 배경에 사용하고, 그 위의 글자에는 짙은 대응색을 사용한다. 흰색 글자는 선명한 블루 실행 버튼과 활성 언어에 사용한다. 상태는 색상 외에도 아이콘과 선택한 언어의 텍스트로 구분한다.

앱·웹 우측 상단의 한국어/EN 스위치는 밝은 라벤더 바탕의 캡슐 형태로 통일한다. 선택한 항목은 Action blue와 흰 글자로 구분하고 키보드 포커스를 표시한다. 정보 버튼은 테두리 없이 표시하며 호버·포커스는 밝은 배경으로 구분한다.

최종 팔레트의 계산 대비: 본문/Canvas **13.12:1**, 보조 글자/흰색 **5.00:1**, 흰색/Action blue **4.98:1**, Teal/Mint **4.63:1**, Purple/Lavender **4.80:1**, Orange/Peach **5.00:1**. 비활성 버튼은 별도의 비활성 표현을 사용한다.

## 타이포그래피와 여백

- 앱·웹: **Noto Sans CJK KR 한 가지 계열**, 실제 Regular/Bold만 사용. 작업 제목 21px, 섹션 15px, 본문 13px, 보조 11~12px. 자폭 100%, 네이티브 DPI·안티앨리어싱과 충분한 하단 여백으로 렌더링한다.
- 웹은 동일 원본의 한글·라틴 WOFF2 서브셋을 사용한다. 외부 폰트 요청이나 합성 굵기·폭 변형을 사용하지 않는다.
- 기본 간격: 4/8/12/16/24px. 카드 모서리 12px, 버튼 7~8px.
- 심볼의 외곽에 폭의 1/8 이상 여백을 둔다. 심볼 비율·프레임 순서·플레이 방향은 유지한다.
- 기본 로고는 밝은 배경에 놓는다. 작은 앱 아이콘에서는 워드마크를 생략한다.

## 소셜 카드 규칙

원본 지침은 `F:\repository-open-graph-template.png`를 확인했다. 최종 PNG는 **1280×640**, 중요 요소의 안전 여백은 **각 변 80px 이상**이다. 템플릿의 40pt 여백 권고와 약 78px 안내선보다 안쪽에 제목·로고·저장소명을 배치했다. 배경 장식만 여백 밖으로 확장한다. 안내선과 템플릿 문구는 결과물에 포함하지 않는다.

GitHub 저장소 **Settings → General → Social preview**에 `assets/social/social-card.png`를 업로드한다. 파일 제작과 HTML의 OG 메타태그 설정은 완료했으며 GitHub 설정 업로드는 별도 작업이다.

## 제작과 라이선스

로고·소셜 카드는 편집 가능한 SVG 원본을 코드로 작성했으며 `python tools/generate_brand_assets.py`로 PNG/ICO를 재생성할 수 있다. 앱과 같은 Noto Sans CJK KR로 렌더링한다. 글꼴과 별도 라이선스는 `assets/fonts/`에 보관한다.

기능 아이콘은 사용자가 제공한 `F:\Backup\fluentui system icons`의 Microsoft Fluent System Icons SVG 25종을 선별했다. 원본은 `assets/icons/`에 보관하고 앱의 `src/fluent_icons.py`에서 의미별로 색상을 적용한다. Microsoft MIT 고지는 `assets/icons/LICENSE`에 포함한다. 새 심볼과 브랜드 자산은 프로젝트 MIT 라이선스를 따른다.
