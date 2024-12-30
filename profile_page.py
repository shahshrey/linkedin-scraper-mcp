from playwright.async_api import Page
import asyncio
from typing import List, Union
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class ProfilePage:
    """Handles LinkedIn profile page interactions and post scraping."""
    
    def __init__(self, page: Page):
        self._page = page
        self._base_url = "https://www.linkedin.com/in"

    async def _navigate_to_profile(self, linkedin_profile_id: str) -> None:
        """Navigate to a specific LinkedIn profile's activity page."""
        try:
            await self._page.goto(
                f"{self._base_url}/{linkedin_profile_id}/recent-activity/all/",
                timeout=60000
            )
        except Exception as e:
            logger.error(f"Failed to navigate to profile '{linkedin_profile_id}': {str(e)}")
            raise

    async def _scroll_page(self, scrolls: int = 2) -> None:
        """Scroll the page to load more content."""
        try:
            for _ in range(scrolls):
                await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Error while scrolling: {str(e)}")
            raise

    def _parse_html_content(self, page_source: str) -> List[BeautifulSoup]:
        """Parse HTML content to find post containers."""
        try:
            linkedin_soup = BeautifulSoup(page_source, "lxml")
            return [
                container
                for container in linkedin_soup.find_all(
                    "div", {"class": "feed-shared-update-v2"}
                )
                if "activity" in container.get("data-urn", "")
            ]
        except Exception as e:
            logger.error(f"Error parsing HTML content: {str(e)}")
            raise

    def _get_post_content(self, container: BeautifulSoup) -> str:
        """Extract post content from a container."""
        try:
            element = container.find("div", {"class": "update-components-text"})
            return element.text.strip() if element else ""
        except Exception as e:
            logger.error(f"Error extracting post content: {str(e)}")
            return ""

    async def scrape_linkedin_posts(self, linkedin_profile_ids: Union[str, List[str]], max_posts: int = 5) -> List[dict]:
        """Scrape posts from one or more LinkedIn profiles."""
        profile_ids = [linkedin_profile_ids] if isinstance(linkedin_profile_ids, str) else linkedin_profile_ids
        all_posts = []

        for profile_id in profile_ids:
            try:
                await self._navigate_to_profile(profile_id)
                await asyncio.sleep(3)
                await self._scroll_page()
                
                page_content = await self._page.content()
                containers = self._parse_html_content(page_content)
                
                posts = [
                    {"content": self._get_post_content(container)}
                    for container in containers
                    if self._get_post_content(container)
                ]
                
                all_posts.extend(posts[:max_posts])
                
            except Exception as e:
                logger.error(f"Error scraping profile {profile_id}: {str(e)}")
                continue
                
        return all_posts 