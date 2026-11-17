/* Local-only UI language: no network request, no account and no build step. */
(() => {
  'use strict';
  const english = {
    "본문으로 바로가기": "Skip to content",
    "VideoBatchConverter 처음으로": "VideoBatchConverter home",
    "주요 메뉴": "Main navigation",
    "사용 방법": "How it works",
    "프리셋": "Presets",
    "궁금한 점": "FAQ",
    "표시 언어": "Display language",
    "WINDOWS VIDEO CONVERTER · 3.0.0": "WINDOWS VIDEO CONVERTER · 3.0.0",
    "영상은 선명하게,": "Keep videos clear,",
    "보관은": "keep storage",
    "가볍게.": "light.",
    "서로 다른 코덱, 4K부터 작은 영상까지.": "Different codecs. From 4K to smaller videos.",
    "하나의 형식으로 통일하거나, 화질을 우선하며": "Bring them into one format, or prioritize quality",
    "고효율 코덱으로 보관 용량을 줄이세요.": "and use efficient codecs to reduce storage.",
    "Windows 64비트 다운로드": "Download for Windows 64-bit",
    "Windows 64비트 다운로드 ↗": "Download for Windows 64-bit ↗",
    "프로그램 살펴보기": "Explore the app",
    "3.0.0 정식 배포 · 2026-11-17 · Windows 64비트 · 첫 실행 시 FFmpeg 자동 설치": "3.0.0 released · 2026-11-17 · Windows 64-bit · FFmpeg installs on first launch",
    "내 PC에서 변환": "Convert locally",
    "원본 유지": "Keep originals",
    "여러 영상 프레임이 겹쳐 하나의 변환 결과가 되는 브랜드 일러스트": "Brand illustration of several video frames coming together as one conversion result",
    "여행.mp4": "Trip.mp4",
    "여행_archive.mp4": "Trip_archive.mp4",
    "여러 코덱 · 원본 영상": "Different codecs · Original videos",
    "새로운 파일로 저장": "Saved as a new file",
    "핵심 기능": "Key features",
    "폴더째 간편하게": "Add whole folders",
    "여러 코덱 · 하위 폴더까지 분석": "Analyze codecs, including subfolders",
    "목적에 맞는 프리셋": "Presets for your purpose",
    "보관부터 업로드까지": "From archiving to uploading",
    "원본과 결과를 안전하게": "Protect your videos",
    "원본 유지 · 기존 결과 건너뛰기": "Keep originals · Skip existing outputs",
    "추가하고, 고르고, 한 번에.": "Add. Choose. Convert together.",
    "실제 프로그램 화면 · FFmpeg으로 생성한 예제 영상 사용": "Actual app screenshot · Example videos generated with FFmpeg",
    "변환할 영상을 모으세요": "Gather your videos",
    "빈 목록을 클릭해 파일·폴더를 함께 고르거나 끌어 놓으세요. 하위 폴더까지 영상의 코덱·해상도를 분석해 담습니다.": "Click the empty queue to choose files and folders, or drag them in. The app analyzes video codecs and resolutions, including subfolders.",
    "로 파일을 추가할 수도 있습니다.": " also adds video files.",
    "나에게 맞는 설정을 고르세요": "Choose your settings",
    "간결한 드롭다운에서 프리셋을 고르고 해상도와 품질을 조정하세요. 마음에 드는 값은 내 프리셋으로 저장해 다시 쓸 수 있습니다.": "Choose a preset from the compact dropdown, then adjust resolution and quality. Save your preferred settings as a custom preset to use again.",
    "결과를 확인하세요": "Review the results",
    "세 가지로 정리한 변환 목적.": "Three presets. Clear purposes.",
    "프리셋을 눌러 설정을 비교해 보세요.": "Select a preset to compare its settings.",
    "내 설정은 사용자 프리셋으로 저장해 다시 사용할 수 있습니다.": "Save your own settings as a custom preset for next time.",
    "변환 프리셋 비교": "Compare conversion presets",
    "아카이빙": "Archive",
    "원본 해상도로, 더 가볍게.": "Source resolution. Less storage.",
    "4K부터 작은 영상까지 원본 해상도와 오디오를 유지합니다. 영상별로 화질을 조절하고, 더 작아진 결과만 HEVC MP4로 보관합니다.": "Keep the source resolution and audio, from 4K to smaller videos. Adapt quality to each source and keep only smaller HEVC MP4 results.",
    "최대 해상도": "Resolution limit",
    "품질 / 비트레이트": "Quality / bitrate",
    "출력 형식": "Container",
    "오디오": "Audio",
    "원본 복사": "Copy original",
    "동시 작업": "Parallel jobs",
    "2개": "2 jobs",
    "저장 위치": "Save location",
    "원본과 같은 폴더": "Beside the original",
    "VBR · 원본 비디오의 80%": "VBR · 80% of source video bitrate",
    "AAC 평균 목표 192 kb/s": "AAC average target 192 kb/s",
    "4K부터 작은 영상까지 원본 해상도와 오디오를 유지합니다. 원본 비디오 비트레이트의 80%를 VBR 목표로 삼고 더 작아진 결과만 HEVC MP4로 보관합니다.": "Keep the source resolution and audio, from 4K to smaller videos. VBR targets 80% of the source video bitrate and only smaller HEVC MP4 results are kept.",
    "최대 720p의 H.264/AAC MP4로 통일합니다. 작은 원본은 그대로 두고 원본 비디오 비트레이트의 80%를 VBR 목표로 사용합니다.": "Convert to H.264/AAC MP4 up to 720p. Smaller sources retain their size, and VBR targets 80% of the source video bitrate.",
    "최대 1080p": "Up to 1080p",
    "최대 720p": "Up to 720p",
    "AAC 최대 192 kbps": "AAC up to 192 kbps",
    "여러 기기에서 편하게 재생.": "Ready for everyday playback.",
    "YouTube·iPad·Android 태블릿을 위한 범용 H.264/AAC MP4입니다. 최대 1080p로 줄이며 작은 원본은 확대하지 않습니다. HDR은 SDR BT.709로 톤 매핑합니다.": "Widely compatible H.264/AAC MP4 for YouTube, iPad and Android tablets. Limit resolution to 1080p without enlarging smaller sources. HDR is tone-mapped to SDR BT.709.",
    "720p로 간편하게 보관·공유.": "Easy to store and share at 720p.",
    "최대 720p의 H.264/AAC MP4로 통일합니다. 작은 원본은 그대로 두고 낮은 해상도에 맞춰 보수적인 품질값을 적용합니다.": "Standardize on H.264/AAC MP4 at up to 720p. Keep smaller sources at their original resolution and use conservative quality settings for lower-resolution video.",
    "여행_1080p.mp4": "Trip_1080p.mp4",
    "여행_720p.mp4": "Trip_720p.mp4",
    "GPU 인코딩에는 해당 코덱을 지원하는 NVIDIA GPU가 필요합니다. 기기·플레이어의 재생 호환성과 원본 오디오 형식을 확인하세요. 출력에는 첫 번째 영상·오디오 트랙을 포함합니다.": "GPU encoding requires an NVIDIA GPU that supports the selected codec. Check playback support on your device and player, and compatibility with the source audio. Outputs contain the first video and audio tracks.",
    "시작하기 전에,": "Before you start,",
    "이것만 확인하세요.": "a few useful details.",
    "처음에는 짧은 영상 한 개로 설정을 확인해 보세요. 필요한 만큼 조정한 뒤 나머지 영상을 함께 처리하면 됩니다.": "Try your settings on one short video first. Adjust as needed, then process the rest together.",
    "변환은 내 PC 안에서.": "Your PC does the conversion.",
    "영상을 서버로 업로드하지 않습니다.": "Videos are never uploaded to a server.",
    "업데이트 확인과 FFmpeg 최초 설치에 인터넷을 사용합니다.": "Update checks and the initial FFmpeg download use the internet.",
    "어떤 파일을 변환할 수 있나요?": "Which files can I convert?",
    "MP4·MKV·AVI·MOV 등 여러 영상의 실제 코덱·해상도·재생 시간을 분석합니다. 기본 출력은 보관용 HEVC와 범용 H.264이며, AV1·VP9 같은 다른 코덱도 사용자 설정에서 선택할 수 있습니다.": "The app analyzes the actual codec, resolution and duration of MP4, MKV, AVI, MOV and other videos. Default presets use HEVC for archiving and H.264 for broad compatibility. You can also choose AV1, VP9 and other codecs in settings.",
    "NVIDIA GPU가 없어도 사용할 수 있나요?": "Can I use it without an NVIDIA GPU?",
    "네. 비디오 코덱에서 CPU 항목을 선택하세요. GPU 항목은 NVIDIA NVENC를 사용하며 AV1 등 각 코덱의 지원 여부는 GPU 세대와 드라이버에 따라 다릅니다. CPU 인코딩은 영상과 설정에 따라 오래 걸릴 수 있습니다.": "Yes. Choose a CPU option under Video codec. GPU options use NVIDIA NVENC; support for each codec, including AV1, depends on your GPU generation and driver. CPU encoding may take longer depending on the video and settings.",
    "원본은 어떻게 되고, 결과는 어디에 저장되나요?": "What happens to my originals, and where are outputs saved?",
    "원본을 유지하고 같은 폴더에 접미사를 붙인 새 파일로 저장합니다. 예를 들어 여행.mp4는 여행_archive.mp4가 됩니다. 기존 결과 파일이 있으면 덮어쓰지 않고 건너뜁니다.": "Original files are preserved. Each output is a new file with a suffix in the same folder, such as Trip.mp4 → Trip_archive.mp4. Existing outputs are skipped rather than overwritten.",
    "용량은 얼마나 줄어드나요?": "How much smaller will my videos be?",
    "중지하거나 변환이 실패하면 어떻게 하나요?": "What if I stop conversion or a file fails?",
    "정상 중지 시 실행·대기 작업을 취소하고 미완성 결과를 정리합니다. 완료한 결과는 유지합니다. 실패한 파일은 작업 기록이 자동으로 열리므로 GPU·오디오 설정이나 저장 공간을 확인한 뒤 다시 시도하세요.": "Stopping cancels running and queued tasks and removes unfinished outputs. Completed outputs are kept. The activity log opens automatically for failures; check GPU and audio settings or available storage, then try again.",
    "내 설정을 프리셋으로 저장할 수 있나요?": "Can I save my own presets?",
    "앱의 프리셋 옆 저장 버튼을 누르고 이름을 입력하세요. 내 프리셋은 재실행 후에도 유지되며 덮어쓰기와 삭제도 할 수 있습니다. 파일 목록이나 폴더 경로는 저장하지 않습니다.": "Click Save beside the preset selector and enter a name. Your presets persist after restarting and can be replaced or deleted. Presets do not store file queues or folder paths.",
    "3.0.0은 어떻게 실행하나요?": "How can I run version 3.0.0?",
    "Windows 64비트 ZIP을 내려받아 폴더 전체를 압축 해제하고 VideoBatchConverter.exe를 실행하세요. EXE와 bin 폴더를 함께 유지하고 첫 실행 시 FFmpeg 자동 설치를 완료하세요.": "Download the Windows 64-bit ZIP, extract the entire folder, and run VideoBatchConverter.exe. Keep the EXE and bin folder together and complete the FFmpeg setup on first launch. See the",
    "README의 설치·소스 실행 안내": "installation and source instructions in the README",
    "를 참고하세요. 정식 배포 파일은": ". For public downloads, check the actual version on",
    "에서 내려받을 수 있습니다.": ".",
    "소중한 영상에, 더 많은 여유를.": "More room for your videos.",
    "저장소 둘러보기": "Browse the repository",
    "© deuxdoom · VideoBatchConverter 3.0.0": "© deuxdoom · VideoBatchConverter 3.0.0",
    "추가 정보": "More information",
    "변경 기록": "Changelog",
    "문제 제보": "Report an issue",
    "VideoBatchConverter 3.0.0 — 영상은 선명하게, 보관은 가볍게.": "VideoBatchConverter 3.0.0 — Clear videos. Lighter storage.",
    "여러 영상의 코덱을 통일하고, 화질 우선의 HEVC 아카이빙으로 보관 용량을 줄이세요. Windows 동영상 일괄 변환기 VideoBatchConverter 3.0.": "Unify video codecs and reduce storage with quality-first HEVC archiving. VideoBatchConverter 3.0, a batch video converter for Windows.",
    "VideoBatchConverter — 영상은 선명하게, 보관은 가볍게.": "VideoBatchConverter — Clear videos. Lighter storage.",
    "파일 추가, 프리셋 선택, 한 번에 변환. 밝고 간결해진 Windows 동영상 변환기 3.0.": "Add files, choose a preset and convert together. A clear, light Windows video converter. Version 3.0.0.",
    "VideoBatchConverter 3.0의 세 프레임 로고와 영상은 선명하게, 보관은 가볍게 슬로건": "VideoBatchConverter 3.0 three-frame logo with the slogan Clear videos. Lighter storage.",
    "VideoBatchConverter 3.0.0": "VideoBatchConverter 3.0.0",
    "H.264 영상을 H.265 · AV1 · VP9로, 여러 파일을 한 번에.": "Convert multiple videos to H.265, AV1, VP9 and more in one batch.",
    "코덱·비트레이트·길이를 목록에서 바로 확인하세요.": "See codec, bitrate and duration directly in the queue.",
    "긴 설정 영역과 하단 진행 표시로 대량 작업을 확인하세요.": "Review large batches with a taller settings panel and progress along the bottom.",
    "VideoBatchConverter 3.0 실제 화면. 왼쪽의 코덱·비트레이트·길이 목록, 오른쪽의 긴 설정 영역과 하단 진행 표시.": "VideoBatchConverter 3.0: codec, bitrate and duration in the queue, a tall settings panel and progress along the bottom.",
    "시작 전 샘플로 예상 용량을 확인합니다. 변환 후에는 완료·실패·결과 제외와 크기를 목록에서 확인하고, 완료 항목 따라가기로 최근 결과를 볼 수 있습니다.": "Check estimated sizes from samples before encoding. Review completed, failed and discarded outputs and their sizes in the queue, or follow the latest result automatically.",
    "원본과 코덱·품질 설정에 따라 다릅니다. 사전 샘플로 추정하고, 원본 이상 크기의 아카이빙 결과는 제외 이유와 크기를 표시합니다. 저장된 결과가 없으면 별도로 알립니다. 원본은 자동 삭제하지 않으며 손실 압축에서 같은 화질을 보장할 수는 없습니다.": "Sizes depend on the source, codec and quality settings. Samples provide an estimate. Archive labels outputs that are not smaller with their sizes and discard reason, and alerts you when no outputs were saved. Originals are never deleted automatically; lossy encoding cannot guarantee identical source quality.",
    "예상 용량이 크면 어떻게 하나요?": "What if the estimated output is too large?",
    "첫 주의 파일에서 멈춰 설정 조정·주의 파일 제외·계속 진행을 선택합니다. CQ/CRF는 숫자를 높이고 비트레이트는 낮추면 용량을 줄이는 방향입니다. 추정값과 실제 크기는 다를 수 있으며 사전 확인은 고급 설정에서 끌 수 있습니다.": "At the first warning, pause to adjust settings, exclude warned files or continue. Increasing CQ/CRF or lowering bitrate tends to reduce size. Estimates can differ from actual outputs. You can turn preflight estimation off in advanced settings.",
    "완료 알림과 종료는 어떻게 동작하나요?": "How do completion alerts and closing work?",
    "배치가 끝나면 짧은 완료음을 한 번 재생하며 설정 창의 일반에서 끌 수 있습니다. 종료할 때는 간단한 확인창을 표시하고, 진행 중인 작업이 있으면 정리한 뒤 닫습니다.": "A short sound plays once when a batch finishes and can be muted under General in Settings. A simple confirmation appears when closing. Running tasks are stopped and cleaned up before the app exits.",
    "프리셋과 품질을 고르면 목록에 영상별 예상 시간이 표시됩니다. 고급 옵션은 우측 상단 설정 창에서 조정하고, 내 프리셋으로 저장해 다시 쓸 수 있습니다.": "Choose a preset and quality to see estimated conversion times in the queue. Adjust advanced options in Settings at the top right, and save your own preset to use again.",
    "예상 시간은 어떻게 계산하나요?": "How is conversion time estimated?",
    "파일 추가·인코딩 설정 변경 시 짧은 실제 샘플로 각 영상의 변환 시간을 추정합니다. 합계는 개별 시간을 더한 값이며 동시 작업 수·PC 부하에 따라 실제 완료 시간은 달라집니다.": "Adding files or changing encoding settings runs short samples to estimate each video's conversion time. The total adds individual times; parallel jobs and PC load can change actual completion time."
};
  const translate = (text, language) => language === 'en' ? (english[text] ?? text) : text;
  const textBindings = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: node => node.parentElement.closest('script, style, noscript, [data-language]') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const source = node.nodeValue.trim();
    if (source in english) textBindings.push({node, source, prefix: node.nodeValue.match(/^\s*/)[0], suffix: node.nodeValue.match(/\s*$/)[0]});
  }
  const attributeBindings = [];
  document.querySelectorAll('[aria-label], [alt], meta[content]').forEach(element => {
    for (const attribute of ['aria-label', 'alt', 'content']) {
      const source = element.getAttribute(attribute);
      if (source in english) attributeBindings.push({element, attribute, source});
    }
  });
  const originalTitle = document.title;
  const profiles = {
    archive: {title:'원본 해상도로, 더 가볍게.',codec:'HEVC · GPU',description:'4K부터 작은 영상까지 원본 해상도와 오디오를 유지합니다. 원본 비디오 비트레이트의 80%를 VBR 목표로 삼고 더 작아진 결과만 HEVC MP4로 보관합니다.',resolution:'원본 유지',quality:'VBR · 원본 비디오의 80%',format:'MP4',audio:'원본 복사',output:'여행_archive.mp4'},
    fullhd: {title:'여러 기기에서 편하게 재생.',codec:'H.264 · GPU',description:'YouTube·iPad·Android 태블릿을 위한 범용 H.264/AAC MP4입니다. 최대 1080p로 줄이며 작은 원본은 확대하지 않습니다. HDR은 SDR BT.709로 톤 매핑합니다.',resolution:'최대 1080p',quality:'VBR · 원본 비디오의 80%',format:'MP4',audio:'AAC 평균 목표 192 kb/s',output:'여행_1080p.mp4'},
    hd720: {title:'720p로 간편하게 보관·공유.',codec:'H.264 · GPU',description:'최대 720p의 H.264/AAC MP4로 통일합니다. 작은 원본은 그대로 두고 원본 비디오 비트레이트의 80%를 VBR 목표로 사용합니다.',resolution:'최대 720p',quality:'VBR · 원본 비디오의 80%',format:'MP4',audio:'AAC 평균 목표 192 kb/s',output:'여행_720p.mp4'}
  };
  let selectedProfile = 'archive';
  let language = 'ko';
  function renderProfile() {
    document.querySelectorAll('[data-profile]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.profile === selectedProfile)));
    for (const [key, value] of Object.entries(profiles[selectedProfile])) {
      const element = document.getElementById('profile-' + (key === 'description' ? 'desc' : key));
      if (element) element.textContent = translate(value, language);
    }
    // Resolution refers to the source size; the tag above refers to source files.
    if (language === 'en' && selectedProfile === 'archive') document.getElementById('profile-resolution').textContent = 'Source resolution';
  }
  function setLanguage(value, remember = true) {
    language = value === 'en' ? 'en' : 'ko';
    document.documentElement.lang = language;
    document.title = translate(originalTitle, language);
    textBindings.forEach(({node, source, prefix, suffix}) => { node.nodeValue = prefix + translate(source, language) + suffix; });
    attributeBindings.forEach(({element, attribute, source}) => element.setAttribute(attribute, translate(source, language)));
    document.querySelector('meta[property="og:locale"]').content = language === 'en' ? 'en_US' : 'ko_KR';
    document.querySelectorAll('[data-language]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.language === language)));
    document.querySelector('.screen-stage img').src = `assets/screenshots/workspace${language === 'en' ? '-en' : ''}.png`;
    renderProfile();
    if (remember) { try { localStorage.setItem('vbc-language', language); } catch { /* Private/file browsing may deny storage. */ } }
  }
  document.querySelectorAll('[data-profile]').forEach(button => button.addEventListener('click', () => { selectedProfile = button.dataset.profile; renderProfile(); }));
  document.querySelectorAll('[data-language]').forEach(button => button.addEventListener('click', () => setLanguage(button.dataset.language)));
  let storedLanguage;
  try { storedLanguage = localStorage.getItem('vbc-language'); } catch { /* Default to Korean when storage is unavailable. */ }
  setLanguage(storedLanguage, false);
})();
