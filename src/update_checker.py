# src/update_checker.py
import requests
import logging
from PyQt6.QtCore import QThread, pyqtSignal

# --- GITHUB REPO 정보 수정 ---
GITHUB_REPO_OWNER = "deuxdoom"
GITHUB_REPO_NAME = "VideoBatchConverter"

class UpdateCheckWorker(QThread):
    result = pyqtSignal(dict)
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        self.api_url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
    
    def run(self):
        try:
            response = requests.get(self.api_url, timeout=5)
            response.raise_for_status()
            latest_release = response.json()
            latest_version = latest_release.get("tag_name")
            release_url = latest_release.get("html_url")

            if latest_version and self.is_newer(latest_version, self.current_version):
                logging.info(f"새 버전 발견: {latest_version}")
                self.result.emit({"update": True, "version": latest_version, "url": release_url})
            else:
                logging.info("현재 최신 버전을 사용 중입니다.")
                self.result.emit({"update": False})
        except requests.RequestException as e:
            logging.warning(f"업데이트 확인 중 네트워크 오류 발생: {e}")
            self.result.emit({"update": False})
        except (ValueError, TypeError):
            logging.warning("업데이트 응답 형식을 읽지 못했습니다.")
            self.result.emit({"update": False})
    
    def is_newer(self, latest_v, current_v):
        try:
            latest = tuple(map(int, latest_v.lstrip('v').split('.')))
            current = tuple(map(int, current_v.lstrip('v').split('.')))
            return latest > current
        except (ValueError, AttributeError):
            logging.error(f"버전 번호 비교 오류: '{latest_v}' vs '{current_v}'")
            return False
