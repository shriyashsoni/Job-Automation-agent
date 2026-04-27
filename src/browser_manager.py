import asyncio
import os
import random

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright


class BrowserManager:
    def __init__(self, headless=False, slow_mo=500):
        self.headless = headless
        self.slow_mo = slow_mo
        self.playwright = None
        self.browser = None
        self.context = None

    async def start(self):
        if not self.playwright:
            self.playwright = await async_playwright().start()
        
        user_data_dir = os.path.abspath("data/browser_profile")
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir)

        if not self.context:
            self.context = await self.playwright.chromium.launch_persistent_context(
                user_data_dir,
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=["--start-maximized"],
                viewport={"width": 1440, "height": 960},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
        return await self.context.new_page()

    async def stop(self):
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None

    async def human_type(self, locator, text, delay=(40, 120)):
        await locator.click()
        # Select all and delete to be sure it's clear
        await locator.press("Control+A")
        await locator.press("Backspace")
        await locator.fill("") # Fallback clear
        for char in str(text):
            await locator.type(char, delay=random.randint(*delay))
            await asyncio.sleep(random.uniform(0.01, 0.04))

    async def fill_or_type(self, locator, text):
        text = "" if text is None else str(text)
        try:
            await locator.fill(text)
        except Exception:
            await self.human_type(locator, text)

    async def upload_file(self, locator, file_path):
        if os.path.exists(file_path):
            await locator.set_input_files(file_path)
            print(f"Uploaded file: {file_path}")
        else:
            print(f"Error: File not found at {file_path}")

    async def click_if_visible(self, page, selectors, timeout=2000):
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                await locator.wait_for(state="visible", timeout=timeout)
                await locator.click()
                return True
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return False

    async def random_delay(self, min_s=1, max_s=3):
        await asyncio.sleep(random.uniform(min_s, max_s))
