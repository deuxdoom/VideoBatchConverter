"""Optional browser QA: pip install playwright; playwright install chromium."""

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--artifacts', type=Path, required=True)
    parser.add_argument('--browser-channel', choices=('chrome', 'msedge'))
    args = parser.parse_args()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report = {'viewports': [], 'profile_switches': 0, 'page_errors': [], 'failed_responses': []}
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True, channel=args.browser_channel)
            page = browser.new_page()
            page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            page.on('response', lambda response: report['failed_responses'].append(response.url) if response.status >= 400 else None)
            page.goto(f'http://127.0.0.1:{server.server_port}/', wait_until='networkidle')
            page.evaluate('document.fonts.ready')
            assert page.evaluate('document.fonts.check(\'16px "Noto Sans CJK KR"\')')
            assert 'Noto Sans CJK KR' in page.locator('body').evaluate('(element) => getComputedStyle(element).fontFamily')
            assert page.title().startswith('VideoBatchConverter 3.0')
            for width, height in ((1440, 1000), (768, 1024), (390, 844), (375, 812)):
                page.set_viewport_size({'width': width, 'height': height})
                page.locator('#workspace').scroll_into_view_if_needed()
                page.wait_for_timeout(150)
                assert page.locator('.screen-stage img').evaluate('(image) => image.complete && image.naturalWidth > 0')
                overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
                assert not overflow, f'Horizontal overflow at {width}px'
                assert page.get_by_role('heading', level=1).is_visible()
                report['viewports'].append({'width': width, 'height': height, 'horizontal_overflow': overflow})
                if width in (1440, 390):
                    page.screenshot(path=str(args.artifacts / f'site-{width}.png'), full_page=True)
            assert page.locator('[data-profile]').count() == 3
            for key, expected in [('fullhd', 'VBR · 원본 비디오의 80%'), ('hd720', 'VBR · 원본 비디오의 80%'), ('archive', 'VBR · 원본 비디오의 80%')]:
                button = page.locator(f'[data-profile="{key}"]')
                button.click()
                assert button.get_attribute('aria-pressed') == 'true'
                assert page.locator('[data-profile][aria-pressed=true]').count() == 1
                assert page.locator('#profile-quality').inner_text() == expected
                assert page.locator('#profile-format').inner_text() == 'MP4'
                assert page.locator('#profile-output').inner_text().endswith('.mp4')
                report['profile_switches'] += 1
            page.locator('.faq details').nth(1).locator('summary').click()
            assert page.locator('.faq details').nth(1).get_attribute('open') is not None
            assert page.locator('.faq details').nth(1).locator('p').is_visible()
            page.set_viewport_size({'width': 1440, 'height': 1000})
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(args.artifacts / 'site-hero.png'))
            english = page.locator('[data-language="en"]')
            english.focus()
            english.press('Space')
            assert page.locator('html').get_attribute('lang') == 'en'
            assert english.get_attribute('aria-pressed') == 'true'
            assert page.title().endswith('Clear videos. Lighter storage.')
            assert page.locator('meta[property="og:locale"]').get_attribute('content') == 'en_US'
            assert page.locator('.screen-stage img').get_attribute('src').endswith('workspace-en.png')
            untranslated = page.evaluate('''() => {
                const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                const texts = [];
                while (walker.nextNode()) {
                    const node = walker.currentNode;
                    if (!node.parentElement.closest('script, style, noscript, [data-language]') && /[가-힣]/.test(node.nodeValue)) texts.push(node.nodeValue.trim());
                }
                return texts;
            }''')
            assert not untranslated, untranslated
            for width, height in ((1440, 1000), (768, 1024), (390, 844), (375, 812)):
                page.set_viewport_size({'width': width, 'height': height})
                page.wait_for_timeout(120)
                overflow = page.evaluate('''() => [...document.querySelectorAll('body *')].filter(element => {
                    const box = element.getBoundingClientRect(); return box.width && (box.right > innerWidth + 1 || box.left < -1);
                }).slice(0, 12).map(element => ({tag: element.tagName, class: element.className, width: element.getBoundingClientRect().width, text: element.textContent.trim().slice(0, 70)}))''')
                if width in (1440, 390):
                    page.screenshot(path=str(args.artifacts / f'site-en-{width}.png'), full_page=True)
                    page.evaluate('window.scrollTo(0,0)')
                    page.screenshot(path=str(args.artifacts / f'site-en-hero-{width}.png'))
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth'), (width, overflow)
            for key in ('fullhd', 'hd720', 'archive'):
                page.locator(f'[data-profile="{key}"]').click()
                assert page.locator('#profile-quality').inner_text().startswith('VBR · 80%')
                assert not page.locator('#profile-desc').evaluate('(element) => /[가-힣]/.test(element.textContent)')
            page.locator('[data-profile="fullhd"]').click()
            page.locator('[data-language="ko"]').click()
            assert page.locator('#profile-title').inner_text() == '여러 기기에서 편하게 재생.'
            assert page.locator('.faq details').nth(1).get_attribute('open') is not None
            page.locator('[data-language="en"]').click()
            assert page.locator('#profile-title').inner_text() == 'Ready for everyday playback.'
            page.reload(wait_until='networkidle')
            assert page.locator('html').get_attribute('lang') == 'en'
            page.locator('[data-language="ko"]').click()
            page.reload(wait_until='networkidle')
            assert page.locator('html').get_attribute('lang') == 'ko'
            report['language_switch'] = {'keyboard': True, 'copy': True, 'profiles_preserved': True, 'faq_preserved': True, 'persistence': True, 'english_viewports': [1440, 768, 390, 375]}
            local_page = browser.new_page()
            local_page.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw new Error('Storage disabled');}})")
            local_page.on('pageerror', lambda error: report['page_errors'].append(str(error)))
            local_page.goto((ROOT / 'index.html').as_uri(), wait_until='networkidle')
            local_page.locator('[data-language="en"]').click()
            assert local_page.locator('html').get_attribute('lang') == 'en'
            assert local_page.locator('#profile-title').inner_text() == 'Source resolution. Less storage.'
            report['language_switch']['local_file_without_storage'] = True
            local_page.close()
            assert not report['page_errors'], report['page_errors']
            assert not report['failed_responses'], report['failed_responses']
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    (args.artifacts / 'site-results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
