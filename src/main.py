import argparse
import asyncio
import os
import csv
import json
from urllib.parse import urlparse

from dotenv import load_dotenv
from playwright.async_api import async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ai_agent import AIAgent
from browser_manager import BrowserManager
from job_searcher import JobSearcher
from resume_parser import ResumeParser
from utils import Logger, safe_print

load_dotenv()


def normalize_key(value):
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in (value or "")).strip("_")


async def describe_field(page, locator, index):
    name = await locator.get_attribute("name") or ""
    field_id = await locator.get_attribute("id") or ""
    placeholder = await locator.get_attribute("placeholder") or ""
    field_type = (await locator.get_attribute("type") or await locator.evaluate("el => el.type || el.tagName")).lower()
    label_text = ""

    if field_id:
        label = page.locator(f"label[for='{field_id}']").first
        try:
            if await label.count():
                label_text = (await label.inner_text()).strip()
        except Exception:
            label_text = ""

    if not label_text:
        try:
            label_text = (await locator.evaluate(
                """
                el => {
                    const parentLabel = el.closest('label');
                    if (parentLabel) return parentLabel.innerText || '';
                    const wrapper = el.closest('div, section, form');
                    if (!wrapper) return '';
                    const candidate = wrapper.querySelector('label, legend, p, span');
                    return candidate ? (candidate.innerText || '') : '';
                }
                """
            )).strip()
        except Exception:
            label_text = ""

    display = label_text or placeholder or name or field_id or f"field_{index}"
    key = normalize_key(name or field_id or label_text or placeholder or f"field_{index}")
    return {
        "key": key,
        "name": name,
        "id": field_id,
        "label": label_text,
        "placeholder": placeholder,
        "type": field_type,
        "display": display,
    }


async def collect_fields(page):
    fields = []
    locators = page.locator("input, textarea, select")
    count = await locators.count()
    for index in range(count):
        locator = locators.nth(index)
        try:
            if not await locator.is_visible():
                continue
            disabled = await locator.get_attribute("disabled")
            readonly = await locator.get_attribute("readonly")
            if disabled is not None or readonly is not None:
                continue
            field = await describe_field(page, locator, index)
            fields.append((locator, field))
        except Exception:
            continue
    return fields


async def fill_form_fields(page, bm, ai_agent, resume_profile, resume_path):
    print("Detecting form fields...")
    fields = await collect_fields(page)
    field_data = [field for _, field in fields]
    print(f"Found {len(field_data)} visible fields.")
    answers = ai_agent.generate_form_answers(resume_profile, field_data)

    filled = 0
    uploaded = False
    skipped = []

    for locator, field in fields:
        field_type = field["type"]
        label = field["display"].lower()

        if field_type == "hidden":
            continue

        if field_type == "file" or any(token in label for token in ["resume", "cv", "cover letter"]):
            if resume_path and not uploaded:
                try:
                    await bm.upload_file(locator, resume_path)
                    uploaded = True
                    filled += 1
                except Exception as exc:
                    skipped.append(f"{field['display']} (upload failed: {exc})")
            continue

        value = answers.get(field["key"])
        if value in [None, ""]:
            value = answers.get(normalize_key(field["display"]))
        if value in [None, ""]:
            skipped.append(field["display"])
            continue

        try:
            if "security code" in label or "verification code" in label:
                # Skip security codes as they usually require manual input or OTP
                skipped.append(f"{field['display']} (Security code required)")
                continue
            elif "email" in label:
                # Use email from profile or environment
                email_to_fill = resume_profile.get("Email") or os.getenv("USER_EMAIL", "your_email@example.com")
                await bm.fill_or_type(locator, email_to_fill)
                filled += 1
            elif field_type in {"text", "email", "tel", "url", "search", "number", "textarea"}:
                # Use the provided email for email fields as well
                email_to_fill = resume_profile.get("Email") or os.getenv("USER_EMAIL", "your_email@example.com")
                val = email_to_fill if field_type == "email" else value
                await bm.fill_or_type(locator, val)
                filled += 1
            elif field_type == "checkbox" and isinstance(value, bool):
                checked = await locator.is_checked()
                if value != checked:
                    if value:
                        await locator.check()
                    else:
                        await locator.uncheck()
                filled += 1
            elif field_type in {"select-one", "select"}:
                await locator.select_option(label=str(value))
                filled += 1
            else:
                await bm.fill_or_type(locator, value)
                filled += 1
        except Exception as exc:
            skipped.append(f"{field['display']} ({exc})")

    return {
        "filled_count": filled,
        "uploaded_resume": uploaded,
        "skipped_fields": skipped[:15],
    }


def detect_blockers(body_text, url, page_html=""):
    lower_text = (body_text or "").lower()
    lower_html = (page_html or "").lower()
    
    # If we see common form fields, it's likely NOT a login wall
    form_indicators = ["first name", "last name", "email", "resume", "cv", "upload", "submit application"]
    has_visible_form = any(indicator in lower_text for indicator in form_indicators)
    
    # Hard login/auth walls
    login_indicators = [
        "create account to apply", "login to apply", "sign up to apply",
        "continue with google", "continue with linkedin", "continue with github",
        "sign in with google", "sign in with linkedin"
    ]
    
    if any(indicator in lower_text for indicator in login_indicators):
        if not has_visible_form:
            return "skipped_login_required"
        
    # Check for OAuth buttons specifically in HTML if no form is visible
    if not has_visible_form and "auth" in lower_html and any(x in lower_html for x in ["google", "linkedin", "github"]):
        return "skipped_login_required"

    # Check for password fields - strong indicator of login wall if no form is visible
    if not has_visible_form and ('type="password"' in lower_html or 'type=\'password\'' in lower_html):
        return "skipped_login_required"

    if "captcha" in lower_text or "verify you are human" in lower_text:
        return "Bot protection detected."
    if "page not found" in lower_text or "job is no longer available" in lower_text:
        return "Job listing appears unavailable."
    return ""


async def extract_company_name(page, url):
    selectors = [
        "meta[property='og:site_name']",
        "[data-testid='company-name']",
        "a[href*='company']",
        "span.company",
    ]
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count():
                content = await locator.get_attribute("content")
                if content:
                    return content.strip()
                text = (await locator.inner_text()).strip()
                if text:
                    return text
        except Exception:
            continue
    hostname = urlparse(url).hostname or ""
    return hostname.replace("www.", "")


async def detect_submission_confirmation(page):
    current_url = page.url.lower()
    
    # 1. Check for Email Verification Required
    verification_keywords = ["confirm your email", "verify your email", "check your inbox", "email verification"]
    body_text = await page.locator("body").inner_text()
    if any(word in body_text.lower() for word in verification_keywords):
        return "email_verification_required", "Email verification message detected."

    # 2. Check for Success/Thank You indicators
    confirmation_selectors = [
        "text=Application submitted",
        "text=Successfully submitted",
        "text=Thank you for applying",
        "text=Thanks for applying",
        "text=We have received your application",
        "text=Your application has been submitted",
        "text=successfully received",
        "text=we'll be in touch",
        "text=thank you for your interest",
    ]
    
    # Check URL change for thank you page
    if any(x in current_url for x in ["thank-you", "thanks", "submitted", "confirmation", "success"]):
        return "applied", "URL changed to confirmation page."

    for selector in confirmation_selectors:
        try:
            locator = page.locator(selector).first
            if await locator.count() and await locator.is_visible():
                return "applied", (await locator.inner_text()).strip()
        except Exception:
            continue
            
    return "submit_failed", ""


def load_application_history(file_path):
    history = set()
    abs_path = os.path.abspath(file_path)
    if os.path.exists(abs_path):
        try:
            with open(abs_path, mode="r", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                for row in reader:
                    if len(row) > 3:
                        url = row[3].strip()
                        if url:
                            history.add(url)
            print(f"DEBUG: Loaded {len(history)} entries from {abs_path}")
        except Exception as e:
            print(f"DEBUG: Failed to load history: {e}")
    else:
        print(f"DEBUG: History file not found at {abs_path}")
    return history


async def run_universal_applier(url, resume_profile, ai_agent, logger, settings, history=None):
    if history and url in history:
        safe_print(f"Skipping already applied URL: {url}")
        return

    # We will try to process LinkedIn jobs as they often redirect to external forms
    bm = BrowserManager(headless=settings.headless, slow_mo=settings.slow_mo)
    page = await bm.start()

    try:
        print(f"Navigating to: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            await page.wait_for_load_state("networkidle", timeout=12000)
        except PlaywrightTimeoutError:
            pass

        body_text = await page.locator("body").inner_text()
        page_html = await page.content()
        blocker = detect_blockers(body_text, url, page_html)
        if blocker:
            status = "Skipped" if blocker != "skipped_login_required" else "skipped_login_required"
            logger.log_application("Unknown", "Unknown", url, 0, status, blocker)
            print(f"Skipping: {blocker}")
            return status

        print("Analyzing job description...")
        match_result = ai_agent.match_job(resume_profile, body_text[:8000])
        score = int(match_result.get("match_score", 0))
        reason = match_result.get("reason", "")
        title = await page.title()
        company = await extract_company_name(page, url)
        safe_print(f"Match Score: {score}% | Reason: {reason}")

        if score < settings.min_score:
            logger.log_application(title, company, url, score, "Skipped", reason)
            print("Match score too low. Skipping...")
            return "Skipped"

        clicked = await bm.click_if_visible(
            page,
            [
                "button:has-text('Apply now')",
                "button:has-text('Apply Now')",
                "button:has-text('Apply')",
                "a:has-text('Apply')",
                "text=Apply now",
                "text=Apply Now",
                "text=Apply",
            ],
            timeout=2500,
        )
        if clicked:
            await asyncio.sleep(2)
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=8000)
            except PlaywrightTimeoutError:
                pass

        fill_result = await fill_form_fields(
            page,
            bm,
            ai_agent,
            resume_profile,
            settings.resume_path,
        )
        safe_print(
            f"Filled {fill_result['filled_count']} fields. "
            f"Resume uploaded: {fill_result['uploaded_resume']}."
        )

        if not settings.auto_submit:
            logger.log_application(title, company, url, score, "Draft Ready", reason)
            print("Auto-submit disabled. Leaving the application at draft stage.")
            return

        if fill_result["filled_count"] == 0 and not fill_result["uploaded_resume"]:
            logger.log_application(title, company, url, score, "Skipped", "No confident field matches found")
            print("No confident field matches found. Skipping submit.")
            return "Skipped"

        submitted = await bm.click_if_visible(
            page,
            [
                "button:has-text('Submit Application')",
                "button:has-text('Submit application')",
                "button:has-text('Submit')",
                "button[type='submit']",
                "text=Submit",
            ],
            timeout=2500,
        )
        if submitted:
            await asyncio.sleep(5)
            # Success detection improvement
            status, message = await detect_submission_confirmation(page)
            
            if status == "email_verification_required":
                print(f"WARNING: Email verification required for {url}")
                logger.log_application(title, company, url, score, "email_verification_required", message)
                return "email_verification_required"
            
            if status == "applied":
                extra_reason = reason if not message else f"{reason} | {message}".strip(" |")
                logger.log_application(title, company, url, score, "applied", extra_reason)
                print(f"Application submitted successfully: {message}")
                return "applied"
            else:
                logger.log_application(title, company, url, score, "submit_failed", "Submit clicked but no success signal detected.")
                print("Submit clicked, but success could not be confirmed.")
                return "submit_failed"
        else:
            logger.log_application(title, company, url, score, "Form Filled", reason)
            safe_print("Form filled, but no submit button was confirmed.")
            return "Form Filled"
    finally:
        await bm.stop()


async def gather_job_urls(searcher, args, page=None):
    job_urls = []
    sources = [source.strip().lower() for source in args.sources.split(",") if source.strip()]
    locations = [location.strip() for location in args.location.split(",") if location.strip()]

    for location in locations:
        for source in sources:
            # Use a fresh, NON-PERSISTENT browser for searching to avoid profile locking
            temp_bm = BrowserManager(headless=True, slow_mo=0)
            # Override start to use non-persistent for search
            async def start_clean():
                if not temp_bm.playwright:
                    temp_bm.playwright = await async_playwright().start()
                browser = await temp_bm.playwright.chromium.launch(headless=True)
                temp_bm.context = await browser.new_context(viewport={"width": 1440, "height": 960})
                return await temp_bm.context.new_page()
            
            temp_bm.start = start_clean
            temp_page = await temp_bm.start()
            try:
                if source == "web3":
                    urls = await searcher.search_web3_career(args.search, location, args.limit, page=temp_page)
                elif source == "cryptojobslist":
                    urls = await searcher.search_cryptojobslist(args.search, location, args.limit, page=temp_page)
                elif source == "remoteok":
                    urls = await searcher.search_remoteok(args.search, args.limit, page=temp_page)
                elif source == "linkedin":
                    # LinkedIn DOES need persistent context, so we handle it specially if needed
                    # For now, skip LinkedIn in searching if it causes issues, or handle it
                    urls = await searcher.search_linkedin_jobs(args.search, location, args.limit, page=temp_page)
                elif source == "official" or source == "curated":
                    urls = await searcher.search_curated_companies(args.limit, page=temp_page)
                elif source == "telegram":
                    urls = await searcher.search_telegram(limit=args.limit, page=temp_page)
                elif source == "workable":
                    urls = await searcher.search_workable(args.search, args.limit, page=temp_page)
                elif source == "additional":
                    urls = await searcher.search_additional_sources(args.search, args.limit, page=temp_page)
                else:
                    continue
                
                if urls:
                    print(f"Successfully gathered {len(urls)} URLs from {source}")
                job_urls.extend(urls)
            except Exception as exc:
                print(f"  [!] {source} search failed: {exc}")
            finally:
                await temp_bm.stop()

    return list(dict.fromkeys(job_urls))[: args.limit]


def build_parser():
    parser = argparse.ArgumentParser(description="Resume Automation Agent")
    parser.add_argument("--url", help="Direct URL of a job listing")
    parser.add_argument("--search", help="Job title or keyword to search for")
    parser.add_argument("--location", default="Remote", help="Comma-separated locations")
    parser.add_argument("--limit", type=int, default=10, help="Number of jobs to process")
    parser.add_argument("--resume", default=os.getenv("RESUME_PATH"), help="Path to resume")
    parser.add_argument("--sources", default="web3,cryptojobslist,remoteok", help="Comma-separated job boards")
    parser.add_argument("--min-score", type=int, default=70, help="Minimum score required to apply")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    parser.add_argument("--auto-submit", action="store_true", help="Submit applications automatically")
    parser.add_argument("--slow-mo", type=int, default=120, help="Playwright slow motion delay in ms")
    return parser


async def main():
    parser = build_parser()
    args = parser.parse_args()
    args.resume_path = args.resume

    ai_agent = AIAgent(provider=os.getenv("AI_PROVIDER", "gemini"))
    parser_tool = ResumeParser(ai_agent=ai_agent)
    logger = Logger()

    if not args.resume:
        raise ValueError("Resume path missing. Set RESUME_PATH or pass --resume.")

    print(f"Loading resume: {args.resume}")
    profile = parser_tool.parse(args.resume)

    # Gather and Apply in a loop
    search_term = args.search or os.getenv("DEFAULT_JOB_SEARCH", "Blockchain Engineer")
    queries = [search_term, "Web3 Developer", "AI Engineer"]
    
    # Continuous Loop Settings
    # Prioritize non-login sources first
    active_sources = ["curated", "telegram", "web3", "cryptojobslist", "workable", "additional"]
    
    # Initialize searcher with a dummy manager
    searcher = JobSearcher(BrowserManager())
    
    print("\nAGENT RUNNING CONTINUOUSLY. Press Ctrl+C to stop.")
    
    while True:
        history = load_application_history(logger.file_path)
        safe_print(f"\n--- Starting new application cycle (History: {len(history)}) ---")
        
        # Expand queries list for more coverage
        all_queries = [search_term, "Web3 Developer", "AI Engineer", "Blockchain Developer", "Fullstack Engineer", "Software Engineer"]
        
        for query in all_queries:
            args.search = query
            for source in active_sources:
                safe_print(f"\nScanning {source} for '{query}'...")
                
                try:
                    # Remove limit for continuous run
                    args.sources = source
                    args.limit = 50 # Increase limit per source scan
                    job_urls = await gather_job_urls(searcher, args)
                    safe_print(f"Found {len(job_urls)} jobs in {source}")
                    if job_urls:
                        safe_print(f"URLs found: {', '.join(job_urls[:3])}...")
                    
                    # Apply immediately to these specific jobs
                    domain_skips = {}
                    for index, url in enumerate(job_urls, start=1):
                        if url in history:
                            continue
                        
                        domain = urlparse(url).netloc
                        # Skip if domain failed too many times
                        if domain_skips.get(domain, 0) >= 3:
                            safe_print(f"  [skip] Domain {domain} failed too many times")
                            continue

                        # Filter out known login-required domains before even trying
                        if any(x in domain for x in ["linkedin.com", "indeed.com", "glassdoor.com", "naukri.com"]):
                            safe_print(f"  [skip] Login-required site: {domain}")
                            history.add(url)
                            continue

                        safe_print(f"[{index}/{len(job_urls)}] Processing: {url}")
                        try:
                            status = await run_universal_applier(url, profile, ai_agent, logger, args, history)
                            history.add(url)
                            if status in ["Skipped", "Failed", "submit_failed", "skipped_login_required"]:
                                domain_skips[domain] = domain_skips.get(domain, 0) + 1
                            else:
                                domain_skips[domain] = 0
                        except Exception as exc:
                            safe_print(f"Error applying to {url}: {exc}")
                            logger.log_application("Error", "Error", url, 0, "Failed", str(exc))
                            domain_skips[domain] = domain_skips.get(domain, 0) + 1
                except Exception as e:
                    safe_print(f"Failed to process source {source}: {e}")

        safe_print("\nFinished full scan cycle. Looping back to start...")
        await asyncio.sleep(60) # Short delay before restarting cycle


if __name__ == "__main__":
    asyncio.run(main())
