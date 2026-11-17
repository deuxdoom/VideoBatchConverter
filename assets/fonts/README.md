# Noto Sans CJK KR

앱과 웹은 **Noto Sans CJK KR 한 가지 글꼴 계열**을 사용한다. Regular/Bold 두 굵기는 같은 계열이며, 별도의 글꼴을 섞거나 가변 폰트를 사용하지 않는다.

## 원본과 배포

- `NotoSansCJKkr-Regular.otf`: `F:\UTILITY\FONT\NotoSans\NotoSansCJKkr-Regular.otf` 원본.
- `NotoSansCJKkr-Bold.otf`: 같은 디렉터리의 Bold 원본. 제목에 합성 굵기를 적용하지 않도록 동봉한다.
- `web/NotoSansCJKkr-{Regular,Bold}.woff2`: 위 원본의 한글·라틴·기호 웹 서브셋. 각각 약 1.24/1.31 MB. 웹은 외부 CDN 없이 로드한다.
- `LICENSE-Noto.txt`: SIL Open Font License 1.1. 원본 내부의 저작권·라이선스 메타데이터도 웹 서브셋에 유지한다. 글꼴은 프로젝트 코드의 MIT 라이선스와 구분한다.

웹 글꼴 재생성: 개발 의존성 설치 후 `python tools/generate_web_fonts.py`. 앱은 원본 OTF 전체를 사용하므로 CJK 파일명에도 대응한다.

## 선택과 렌더링

Pretendard JP Variable과 Noto Sans CJK KR을 각각 단독으로 100%/125%/150% 배율에서 비교했다. 제목과 한글 설명의 상하 공간이 여유로운 Noto Sans CJK KR을 최종 선택했다. 비교 캡처는 커밋 제외 `.local/verification/font-comparison/`에 보존한다.

앱은 `src/fonts.py`에서 Regular/Bold를 등록하고 **No hinting (`QFont.PreferNoHinting`)**, 원본 윤곽선과 그레이스케일 안티앨리어싱을 사용한다. 자폭 100%와 네이티브 DPI를 유지한다. 수직 힌팅에서 보이던 얇고 거친 획을 Windows 실화면에서 비교해 변경했다. Qt API의 힌팅 옵션은 [QFont 문서](https://doc.qt.io/qt-6.11/qfont.html#HintingPreference-enum)를 참고한다.

Fusion 스타일을 적용한 다음 앱·뷰·헤더·메뉴의 기본 글꼴을 설정한다. 드롭다운과 파일 선택 창은 생성·스타일 적용 후 내부 뷰에도 같은 정책을 적용한다. 전역 `QWidget` 스타일시트에서 글꼴 계열·크기를 중복 지정하면 목록 그리기에 기본 힌팅이 다시 적용되므로 앱 기본 글꼴을 사용하고 필요한 크기·굵기만 개별 지정한다.

라벨에는 하단 여백을 더하고 두 줄 설명의 최소 높이를 글꼴 메트릭으로 계산한다. 목록의 직접 그리기 영역도 글자 높이보다 넉넉하게 확보한다. `tools/check_windows_ui.py`는 실제 Windows 플러그인에서 배율과 한·영 화면·팝업·파일 선택 창을 검사한다.

웹은 동일한 Noto 계열의 WOFF2 Regular/Bold를 사용하고 합성 굵기·글자 폭 변형을 끈다.
