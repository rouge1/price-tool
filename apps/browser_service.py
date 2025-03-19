from playwright.async_api import async_playwright, TimeoutError
import logging
import shutil
import os
import asyncio

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

        page = None
        try:
            page = await self.context.new_page()
            
            # Create a dialog handler function
            async def handle_dialog(dialog):
                await dialog.accept()
            
            # Set up automatic dialog handling
            page.on("dialog", handle_dialog)
            
            # Try with a less strict waiting condition first
            try:
                # First try with domcontentloaded which is faster
                logger.info(f"Navigating to {url} with domcontentloaded wait")
                await page.goto(url, wait_until='domcontentloaded', timeout=15000)
                
                # Then wait for the page to become visually stable
                logger.info("Waiting for load state...")
                await page.wait_for_load_state('load', timeout=10000)
                
                # Try to wait for network to be idle, but don't fail if it times out
                try:
                    logger.info("Waiting for network idle...")
                    await page.wait_for_load_state('networkidle', timeout=5000)
                except TimeoutError:
                    logger.warning("Network idle timeout - continuing anyway")
            except TimeoutError as e:
                # If domcontentloaded times out, we have a serious problem
                logger.error(f"Initial page load failed: {e}")
                raise
            
            logger.info("Page loaded successfully")
            
            # Jiggle mouse to help with initial page loading
            await self._jiggle_mouse(page)
            
            # Give the page a moment to settle
            await page.wait_for_timeout(2000)
            
            # Jiggle the mouse to simulate human behavior and potentially trigger hover elements
            await self._jiggle_mouse(page)
            
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
            
            # Try each selector with a short timeout
            for selector in button_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=500)
                    if button:
                        await button.click()
                        await page.wait_for_timeout(500)
                except Exception:
                    continue

            # Check if page has content before taking screenshot
            body_content = await page.evaluate("document.body.textContent.length")
            if body_content < 50:  # Arbitrary threshold for empty/error pages
                logger.warning(f"Page content seems minimal ({body_content} chars), might be an error page")
            
            # Gentle scroll to trigger lazy loading
            await page.evaluate("window.scrollTo(0, 300)")
            await page.wait_for_timeout(1000)
            
            # More mouse movement after scrolling
            await self._jiggle_mouse(page)
            
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)  # Wait for scrolling to settle
            
            # Take screenshot
            logger.info("Taking screenshot")
            screenshot_bytes = await page.screenshot(
                full_page=False,
                type='jpeg',
                quality=90
            )
            
            await page.close()  # Close the page properly
            logger.info("Screenshot captured successfully")
            return screenshot_bytes

        except Exception as e:
            logger.error(f"Screenshot error: {str(e)}")
            if page:
                # Try to get page error information if available
                try:
                    url_status = await page.evaluate("() => ({ url: window.location.href, title: document.title })")
                    logger.error(f"Page state at error: URL={url_status.get('url')}, Title={url_status.get('title')}")
                except:
                    pass
                    
                try:
                    await page.close()
                except:
                    pass
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
            self._initialized = False

    async def _jiggle_mouse(self, page):
        """Simulate mouse movement across the page to appear more human-like and trigger hover elements."""
        try:
            # Get page dimensions
            dimensions = await page.evaluate("""
                () => {
                    return {
                        width: Math.max(document.documentElement.clientWidth, window.innerWidth || 0),
                        height: Math.max(document.documentElement.clientHeight, window.innerHeight || 0)
                    }
                }
            """)
            
            width = dimensions['width']
            height = dimensions['height']
            
            # Create some random points within the viewport to move to
            points = [
                {'x': width * 0.1, 'y': height * 0.1},  # top-left
                {'x': width * 0.5, 'y': height * 0.2},  # top-center
                {'x': width * 0.8, 'y': height * 0.3},  # top-right
                {'x': width * 0.3, 'y': height * 0.5},  # middle-left
                {'x': width * 0.7, 'y': height * 0.6},  # middle-right
                {'x': width * 0.2, 'y': height * 0.8},  # bottom-left
                {'x': width * 0.6, 'y': height * 0.7},  # bottom-middle
                {'x': width * 0.9, 'y': height * 0.9},  # bottom-right
            ]
            
            # Move the mouse to several points
            for point in points:
                await page.mouse.move(point['x'], point['y'])
                # Random small pause between movements (between 50-200ms)
                await page.wait_for_timeout(50 + (150 * (point['x'] / width)))
                
            logger.debug("Mouse jiggle complete")
            
        except Exception as e:
            # Don't let mouse jiggling errors affect the main flow
            logger.warning(f"Mouse jiggle error (non-critical): {str(e)}")
            
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()