from playwright.async_api import Page
import asyncio
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class SearchPage:
    """Handles LinkedIn search page interactions and connection requests."""
    
    def __init__(self, page: Page):
        self._page = page
        self._base_url = "https://www.linkedin.com/search/results/people"

    async def _navigate_to_search(self, search_query: str) -> None:
        """Navigate to LinkedIn search results for the given query."""
        try:
            search_url = f"{self._base_url}/?keywords={search_query}"
            logger.debug(f"Navigating to search URL: {search_url}")
            await self._page.goto(search_url)
            await self._page.wait_for_timeout(2000)
            logger.info("Search page loaded.")
        except Exception as e:
            logger.error(f"Failed to navigate to search page: {str(e)}")
            raise

    async def _get_profile_info(self, button) -> Dict[str, str]:
        """Extract profile information using the existing selectors."""
        try:
            # Try the first selector pattern
            profile_card = await button.evaluate("""
                button => {
                    const container = button.closest('.entity-result__item');
                    if (!container) return null;
                    const nameElement = container.querySelector('.entity-result__title-text a');
                    const titleElement = container.querySelector('.entity-result__primary-subtitle');
                    const locationElement = container.querySelector('.entity-result__secondary-subtitle');
                    return {
                        name: nameElement ? nameElement.innerText.trim() : 'Unknown Profile',
                        profileUrl: nameElement ? nameElement.href : '',
                        title: titleElement ? titleElement.innerText.trim() : '',
                        location: locationElement ? locationElement.innerText.trim() : ''
                    };
                }
            """)
            
            # If first pattern fails, try the alternative selector
            if not profile_card or not profile_card.get('name'):
                logger.warning("Profile information not found, trying alternative selector...")
                profile_card = await button.evaluate("""
                    button => {
                        const container = button.closest('.iLNPXRzIPSRzJxVVZISWYouxrvwqQ');
                        if (!container) return null;
                        const nameElement = container.querySelector('.vjvKoXFFJtfnpBNnkgFTzWnDmsSASvTcGEESnk a');
                        const titleElement = container.querySelector('.hnypMlQNtRKZTJxKVVHfxzWpjYbYocHvxY');
                        const locationElement = container.querySelector('.entity-result__secondary-subtitle');
                        return {
                            name: nameElement ? nameElement.innerText.trim() : 'Unknown Profile',
                            profileUrl: nameElement ? nameElement.href : '',
                            title: titleElement ? titleElement.innerText.trim() : '',
                            location: locationElement ? locationElement.innerText.trim() : ''
                        };
                    }
                """)

            if not profile_card or not profile_card.get('name'):
                logger.warning("Profile card not found")
                return None

            # Extract profile ID from URL if available
            if profile_card.get('profileUrl'):
                try:
                    profile_id = profile_card['profileUrl'].split('/in/')[1].split('/')[0]
                    profile_card['profileId'] = profile_id
                except:
                    profile_card['profileId'] = ''

            return profile_card
        except Exception as e:
            logger.error(f"Error extracting profile info: {str(e)}")
            return None

    async def _send_connection_request(self, button, custom_note: str = "") -> Dict[str, str]:
        """Send a connection request to a profile."""
        try:
            await button.click()
            await self._page.wait_for_timeout(1000)
            
            if custom_note:
                logger.debug("Adding custom note to connection request.")
                add_note_button = await self._page.wait_for_selector("button:has-text('Add a note')", timeout=2000)
                if add_note_button:
                    await add_note_button.click()
                    await self._page.wait_for_timeout(500)
                    await self._page.fill("textarea[name='message']", custom_note)
                    await self._page.wait_for_timeout(5000)
                    send_button = await self._page.wait_for_selector("button:has-text('Send')", timeout=2000)
                    if send_button:
                        await send_button.click()
            else:
                send_button = await self._page.wait_for_selector("button:has-text('Send')", timeout=2000)
                if send_button:
                    await send_button.click()
            
            return {"status": "success"}
        except Exception as e:
            logger.error(f"Error sending connection request: {str(e)}")
            return {"status": "failed", "error": str(e)}

    async def send_connection_requests(
        self,
        search_query: str,
        max_connections: int,
        custom_note: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Search for profiles and send connection requests.
        
        Args:
            search_query: Search query to find LinkedIn profiles
            max_connections: Maximum number of connection requests to send
            custom_note: Optional custom note to include with connection requests
            
        Returns:
            List of results containing profile information and connection status
        """
        try:
            await self._navigate_to_search(search_query)
            sent_requests = 0
            results = []
            
            for _ in range(min(max_connections, 3)):  # Limit page navigation to 3 pages
                connect_buttons = await self._page.query_selector_all("button:has-text('Connect')")
                logger.debug(f"Found {len(connect_buttons)} connect buttons on the page.")

                for button in connect_buttons[:max_connections]:
                    try:
                        # Get profile info before clicking connect
                        profile_info = await self._get_profile_info(button)
                        
                        # Format custom note with profile info if provided
                        formatted_note = None
                        if custom_note:
                            try:
                                # Use dict.get() with default values to handle missing fields
                                formatted_note = custom_note.format(
                                    name=profile_info.get('name', '[Name]'),
                                    title=profile_info.get('title', '[Title]'),
                                    location=profile_info.get('location', '[Location]')
                                )
                            except KeyError as e:
                                logger.warning(f"Failed to format custom note - missing key: {e}")
                                formatted_note = custom_note  # Fall back to unformatted note
                            except ValueError as e:
                                logger.warning(f"Failed to format custom note - invalid format: {e}")
                                formatted_note = custom_note  # Fall back to unformatted note

                        # Click connect button
                        await button.click()
                        
                        # If we have a formatted note, use it
                        if formatted_note:
                            # Click "Add a note" button
                            add_note_button = await self._page.wait_for_selector('button[aria-label="Add a note"]')
                            await add_note_button.click()
                            
                            # Fill in the custom note
                            note_textarea = await self._page.wait_for_selector('#custom-message')
                            await note_textarea.fill(formatted_note)
                            
                            # Click Send
                            send_button = await self._page.wait_for_selector('button[aria-label="Send now"]')
                            await send_button.click()
                        else:
                            # Click "Send without note"
                            send_button = await self._page.wait_for_selector('button[aria-label="Send without a note"]')
                            await send_button.click()

                        results.append({
                            "status": "success",
                            "profile": profile_info
                        })

                    except Exception as e:
                        results.append({
                            "status": "error",
                            "error": str(e),
                            "profile": profile_info if 'profile_info' in locals() else None
                        })

                    await self._page.wait_for_timeout(1000)
                
                if sent_requests >= max_connections:
                    break
                
                # Try to navigate to next page
                next_button = await self._page.query_selector("button[aria-label='Next']")
                if next_button:
                    logger.info("Navigating to the next page of search results.")
                    await next_button.click()
                    await self._page.wait_for_timeout(2000)
                else:
                    logger.info("No more pages to navigate.")
                    break
            
            return results
            
        except Exception as e:
            logger.error(f"Error sending connection requests: {str(e)}")
            raise 