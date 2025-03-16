from playwright.async_api import async_playwright
import logging
import shutil
import os

logger = logging.getLogger(__name__)

class BrowserService:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self._initialized = False
        self.persistent_page = None

    def _find_browser(self):
        """Find installed browsers"""
        # Check for Chrome
        chrome_paths = [
            '/usr/bin/google-chrome',
            '/usr/bin/chrome',
            '/usr/bin/chromium',
            '/usr/bin/chromium-browser'
        ]
        for path in chrome_paths:
            if os.path.exists(path):
                return {'type': 'chromium', 'channel': 'chrome', 'executablePath': path}

        # Check for Firefox
        firefox_paths = [
            '/usr/bin/firefox',
            '/usr/bin/firefox-esr'
        ]
        for path in firefox_paths:
            if os.path.exists(path):
                return {'type': 'firefox', 'executablePath': path}

        return None

    async def init_browser(self):
        if self._initialized:
            return True
            
        try:
            self.playwright = await async_playwright().start()
            
            # Find system browser
            browser_config = self._find_browser()
            if not browser_config:
                logger.error("No supported browser found")
                return False

            if browser_config['type'] == 'chromium':
                self.browser = await self.playwright.chromium.launch(
                    headless=False,
                    channel=browser_config.get('channel'),
                    executable_path=browser_config['executablePath'],
                    args=[
                        '--start-maximized',
                        '--window-size=1280,900',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                    ]
                )
            else:  # Firefox
                self.browser = await self.playwright.firefox.launch(
                    headless=False,
                    executable_path=browser_config['executablePath'],
                    args=[
                        '--window-size=1280,900'
                    ]
                )

            self.context = await self.browser.new_context(
                viewport={'width': 1280, 'height': 900},
                user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
            
            # Create a persistent page that stays open
            self.persistent_page = await self.context.new_page()
            await self.persistent_page.goto('https://www.google.com')
            
            self._initialized = True
            logger.info(f"Browser service initialized successfully using {browser_config['executablePath']}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}")
            return False

    async def get_screenshot(self, url):
        if not self.context:
            if not await self.init_browser():
                raise Exception("Browser not available")

        try:
            page = await self.context.new_page()
            
            # Set up automatic dialog handling
            page.on("dialog", lambda dialog: asyncio.create_task(dialog.accept()))
            
            await page.goto(url, wait_until='load', timeout=30000)
            await page.wait_for_timeout(2000)
            
            # List of common positive action button selectors
            button_selectors = [
                # Cookie and privacy buttons
                '[id*="cookie"] button', 
                '[class*="cookie"] button',
                '[class*="popup"] button',
                # Accept/OK buttons by text
                'button:has-text("Accept")',
                'button:has-text("OK")',
                'button:has-text("Yes")',
                'button:has-text("Allow")',
                'button:has-text("I Accept")',
                'button:has-text("Continue")',
                # Accept/OK buttons by class/id
                '[class*="accept"]',
                '[class*="allow"]',
                '[id*="accept"]',
                '[id*="allow"]',
                # Common popup close buttons
                '.close-button',
                '.modal-close',
                '[class*="close"]',
                '[aria-label="Close"]'
            ]
            
            # Try each selector
            for selector in button_selectors:
                try:
                    # Look for the button and click it if found
                    button = await page.wait_for_selector(selector, timeout=500)
                    if button:
                        await button.click()
                        await page.wait_for_timeout(500)  # Wait for popup to clear
                except:
                    continue

            await page.evaluate("window.scrollTo(0, 300)")
            await page.wait_for_timeout(1000)
            await page.evaluate("window.scrollTo(0, 0)")
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(
                full_page=False,
                type='jpeg',
                quality=90
            )
            
            await page.close()
            return screenshot_bytes

        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            raise

    async def cleanup(self):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
        finally:
            self.playwright = None
            self.browser = None
            self.context = None

    async def __adel__(self):
        await self.cleanup()
