import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = 'https://igreval.maharashtra.gov.in/eASR2.0/eASRCommon.aspx?hDistName='
DISTRICT = 'Thane'
YEAR = '2023-2024'
TALUKA = 'Thane'
VILLAGE_CONTAINS = 'Majivade'
SURVEY_NO = '121'

DUMP_DIR = Path(__file__).parent / 'debug_dump'


def ensure_dump_dir():
    DUMP_DIR.mkdir(parents=True, exist_ok=True)


def dump_text(path: Path, text: str):
    path.write_text(text, encoding='utf-8', errors='ignore')


def find_context_with_selector(page, selector: str, timeout: int = 10000):
    try:
        page.wait_for_selector(selector, timeout=timeout)
        return page
    except Exception:
        pass
    for fr in page.frames:
        try:
            fr.wait_for_selector(selector, timeout=2000)
            return fr
        except Exception:
            continue
    return None


def click_text_any(page, text: str, exact: bool = True) -> bool:
    targets = [page] + [f for f in page.frames]
    # Diagnostics: list text inputs
    for ctx in targets:
        try:
            inputs = ctx.locator("//input[@type='text']")
            cnt = inputs.count()
            print(f"[Probe] Found {cnt} text inputs in a frame")
            for i in range(min(cnt, 10)):
                node = inputs.nth(i)
                try:
                    _id = node.get_attribute('id')
                    _name = node.get_attribute('name')
                    _ph = node.get_attribute('placeholder')
                    print(f"  - input[{i}] id={_id} name={_name} placeholder={_ph}")
                except Exception:
                    pass
        except Exception:
            continue
    for ctx in targets:
        try:
            loc = ctx.get_by_text(text, exact=exact)
            if loc.count() > 0:
                print(f"[Probe] Click '{text}' (exact={exact})")
                loc.first.click()
                return True
        except Exception:
            continue
    return False

def log_checked_radio(page, prefix: str = ""):
    targets = [page] + [f for f in page.frames]
    for ctx in targets:
        try:
            checked = ctx.locator("input[type='radio']:checked")
            if checked.count() > 0:
                try:
                    rid = checked.first.get_attribute('id')
                    label = ''
                    if rid:
                        lab = ctx.locator(f"label[for='{rid}']")
                        if lab.count() > 0:
                            label = lab.first.inner_text().strip()
                    if not label:
                        label = checked.first.evaluate("el => (el.closest('label')?.innerText) || (el.parentElement?.innerText) || '' ") or ''
                    print(f"[Probe] {prefix}Checked radio label: '{label}'")
                    return
                except Exception:
                    pass
        except Exception:
            continue

def select_radio_option(page, option_label: str) -> bool:
    # 1) Try clicking text
    if click_text_any(page, option_label, exact=True):
        return True
    if click_text_any(page, option_label, exact=False):
        return True
    # 2) Try label->radio association
    if ensure_radio_selected(page, option_label):
        return True
    # 3) Try proximity: find element containing text and click nearest radio
    targets = [page] + [f for f in page.frames]
    for ctx in targets:
        try:
            el = ctx.locator(f"//*[contains(normalize-space(.), '{option_label}')] ")
            if el.count() == 0:
                continue
            # Following radio
            r = ctx.locator(f"//*[contains(normalize-space(.), '{option_label}')]/following::input[@type='radio'][1]")
            if r.count() > 0:
                try:
                    r.first.evaluate("el => { el.click(); el.checked = true; el.dispatchEvent(new Event('change', {bubbles:true})); }")
                    return True
                except Exception:
                    pass
            # Preceding radio
            r = ctx.locator(f"//*[contains(normalize-space(.), '{option_label}')]/preceding::input[@type='radio'][1]")
            if r.count() > 0:
                try:
                    r.first.evaluate("el => { el.click(); el.checked = true; el.dispatchEvent(new Event('change', {bubbles:true})); }")
                    return True
                except Exception:
                    pass
        except Exception:
            continue
    return False

def ensure_radio_selected(page, label_text: str) -> bool:
    targets = [page] + [f for f in page.frames]
    for ctx in targets:
        try:
            lab = ctx.locator(f"//label[contains(normalize-space(.), '{label_text}')]")
            if lab.count() == 0:
                continue
            for xp in [
                f"//label[contains(normalize-space(.), '{label_text}')]/following::input[@type='radio'][1]",
                f"//label[contains(normalize-space(.), '{label_text}')]/preceding::input[@type='radio'][1]",
            ]:
                r = ctx.locator(xp)
                if r.count() > 0:
                    try:
                        r.first.evaluate("el => { el.checked = true; el.dispatchEvent(new Event('change', {bubbles:true})); el.dispatchEvent(new Event('click', {bubbles:true})); }")
                        return True
                    except Exception:
                        pass
        except Exception:
            continue
    return False


def select_option_label(page, selector: str, label: str):
    ctx = find_context_with_selector(page, selector)
    if ctx is None:
        raise RuntimeError(f"Selector not found: {selector}")
    print(f"[Probe] Select '{label}' on {selector}")
    ctx.select_option(selector, label=label)
    time.sleep(0.8)


def fill_survey_input(page, value: str):
    # Wait a bit after selecting radio
    time.sleep(0.5)
    try:
        page.wait_for_selector("input", timeout=3000)
    except Exception:
        pass

    strategies = []
    # 1) Label text
    strategies.append(lambda ctx: ctx.locator("//label[contains(normalize-space(.), 'Enter Survey No')]/following::input[1]"))
    strategies.append(lambda ctx: ctx.locator("//*[contains(normalize-space(.), 'Enter Survey No')]/following::input[1]"))
    # 2) aria-label / placeholder
    for key in ['survey', 'enter survey', 'survey no']:
        strategies.append(lambda ctx, k=key: ctx.locator(f"//input[contains(translate(@aria-label,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{k}')]"))
        strategies.append(lambda ctx, k=key: ctx.locator(f"//input[contains(translate(@placeholder,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), '{k}')]"))
    # 3) id/name contains
    for frag in ['Survey', 'survey', 'txtSurvey', 'txtSearch', 'Search', 'srch']:
        strategies.append(lambda ctx, f=frag: ctx.locator(f"//input[contains(@id, '{f}') and (@type='text' or not(@type))]"))
        strategies.append(lambda ctx, f=frag: ctx.locator(f"//input[contains(@name, '{f}') and (@type='text' or not(@type))]"))
    # 4) input immediately before Search button
    strategies.append(lambda ctx: ctx.locator("(//button[contains(., 'Search')] | //input[@type='submit' and contains(@value,'Search')] | //input[@type='button' and contains(@value,'Search')] | //a[contains(.,'Search')])[1]/preceding::input[@type='text'][1]"))
    # 5) Fallback: last text input on page
    strategies.append(lambda ctx: ctx.locator("(//input[@type='text'])[last()]"))
    # 6) Table layout: label cell then input in next cell
    strategies.append(lambda ctx: ctx.locator("//td[contains(normalize-space(.), 'Enter Survey No')]/following-sibling::td//input"))
    strategies.append(lambda ctx: ctx.locator("//td[contains(normalize-space(.), 'Enter Survey No')]/following::input[1]"))

    targets = [page] + [f for f in page.frames]
    for ctx in targets:
        for build in strategies:
            try:
                loc = build(ctx)
                if loc and loc.count() > 0:
                    try:
                        loc.first.wait_for(state='visible', timeout=1000)
                    except Exception:
                        pass
                    print(f"[Probe] Fill survey input with '{value}'")
                    loc.first.fill(value)
                    return ctx, loc.first
            except Exception:
                continue
    raise RuntimeError("Survey input not found")


def dump_frames_and_tables(page):
    # Dump main frame + all child frames contents and all tables
    idx = 0
    for fr in [page] + [f for f in page.frames]:
        try:
            html = fr.content()
            dump_text(DUMP_DIR / f"frame_{idx}_content.html", html)
            tables = fr.locator('table')
            tcount = tables.count()
            print(f"[Probe] Frame {idx} has {tcount} tables")
            for i in range(tcount):
                tloc = tables.nth(i)
                try:
                    outer = tloc.evaluate("el => el.outerHTML")
                except Exception:
                    outer = '<table>' + tloc.inner_html() + '</table>'
                dump_text(DUMP_DIR / f"frame_{idx}_table_{i}.html", outer)
            idx += 1
        except Exception as e:
            print(f"[Probe] Dump error on frame {idx}: {e}")
            idx += 1
            continue


def main():
    ensure_dump_dir()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        page = browser.new_page()
        page.set_default_timeout(20000)

        # Navigate
        url = f"{BASE_URL}{DISTRICT}"
        print(f"[Probe] Goto: {url}")
        page.goto(url, wait_until='domcontentloaded')
        try:
            page.wait_for_load_state('networkidle', timeout=15000)
        except Exception:
            pass

        # Year
        select_option_label(page, '#ctl00_ContentPlaceHolder5_ddlYear', YEAR)

        # Taluka
        select_option_label(page, '#ctl00_ContentPlaceHolder5_ddlTaluka', TALUKA)

        # Village (contains)
        print(f"[Probe] Select village contains: {VILLAGE_CONTAINS}")
        ctx_v = find_context_with_selector(page, '#ctl00_ContentPlaceHolder5_ddlVillage') or page
        opts = ctx_v.locator('#ctl00_ContentPlaceHolder5_ddlVillage option')
        val = None
        for i in range(opts.count()):
            text = opts.nth(i).inner_text().strip()
            if VILLAGE_CONTAINS.lower() in text.lower():
                val = opts.nth(i).get_attribute('value')
                print(f"[Probe] Village match: {text}")
                break
        if val:
            ctx_v.select_option('#ctl00_ContentPlaceHolder5_ddlVillage', value=val)
        else:
            raise RuntimeError("Village option not found by contains")
        time.sleep(0.8)

        # Radio: Survey No.
        if not select_radio_option(page, 'Survey No.') and not select_radio_option(page, 'Survey No'):
            print("[Probe] Could not force-select 'Survey No.' radio")
        # Give UI time to render the input
        try:
            page.wait_for_selector("//*[contains(normalize-space(.), 'Enter Survey No')]/following::input[1]", timeout=8000)
        except Exception:
            pass
        try:
            page.wait_for_selector("input", timeout=8000)
        except Exception:
            pass
        time.sleep(1.2)
        log_checked_radio(page, prefix="After Survey selection: ")

        # Fill survey
        try:
            ctx_input, input_loc = fill_survey_input(page, SURVEY_NO)
        except Exception as e:
            print(f"[Probe] First attempt failed: {e}. Dumping frames immediately for diagnostics...")
            dump_frames_and_tables(page)
            # Retry once more after a short delay
            time.sleep(2)
            ctx_input, input_loc = fill_survey_input(page, SURVEY_NO)

        # Click Search
        if not click_text_any(page, 'Search', exact=True):
            click_text_any(page, 'Search', exact=False)
        try:
            page.wait_for_load_state('networkidle', timeout=5000)
        except Exception:
            pass
        time.sleep(1.0)

        # Dump everything
        print("[Probe] Dumping page, frames and tables to debug_dump/ ...")
        dump_frames_and_tables(page)
        print("[Probe] Done. Please zip and share the debug_dump folder.")

        # Keep browser open briefly
        time.sleep(2)
        browser.close()


if __name__ == '__main__':
    main()
