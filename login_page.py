import logging
import os
from playwright.async_api import Page, TimeoutError
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoginPage:
    """Handles LinkedIn login page interactions."""
    
    def __init__(self, page: Page):
        self.page = page
        self.email_input = page.get_by_label("Email or Phone")
        self.password_input = page.get_by_label("Password")
        self.login_button = page.locator('button[data-litms-control-urn="login-submit"]')

    async def login(self, email: Optional[str] = None, password: Optional[str] = None) -> bool:
        """
        Handle LinkedIn login with proper error handling and logging.
        
        Args:
            email: Optional email override (defaults to env var)
            password: Optional password override (defaults to env var)
            
        Returns:
            bool: True if login successful, False otherwise
            
        Raises:
            ValueError: If credentials not provided
            Exception: For other login failures
        """
        if not email or not password:
            raise ValueError("Email and password must be provided")

        try:
            logger.info("Navigating to LinkedIn login page")
            await self.page.goto("https://www.linkedin.com/login")
            
            logger.debug("Filling login credentials")
            await self.email_input.fill(email)
            await self.password_input.fill(password)
            
            logger.debug("Clicking login button")
            await self.login_button.click()

            logger.info("Waiting for redirect to feed page")
            await self.page.wait_for_url("https://www.linkedin.com/feed/", timeout=15000)
            
            logger.info("Login successful")
            return True
            
        except TimeoutError:
            logger.error("Login timeout - failed to redirect to feed page")
            raise Exception("Login failed: Timeout waiting for redirect")
        except Exception as e:
            logger.error(f"Login failed with error: {str(e)}")
            raise Exception(f"Login failed: {str(e)}")

    async def is_logged_in(self) -> bool:
        """Check if user is currently logged in to LinkedIn."""
        try:
            current_url = self.page.url
            return "feed" in current_url or "mynetwork" in current_url
        except Exception as e:
            logger.error(f"Error checking login status: {str(e)}")
            return False
