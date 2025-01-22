"""Script to scrape LinkedIn profiles and save them locally."""

from scripts.base_script import BaseScript
from integrations.linkedin_client import get_linkedin_client
from config.secrets import LINKEDIN_EMAIL, LINKEDIN_PASSWORD
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class LinkedInScraper(BaseScript):
    def __init__(self):
        super().__init__()
        self.client = get_linkedin_client(LINKEDIN_EMAIL, LINKEDIN_PASSWORD)
    
    @property
    def name(self) -> str:
        return "linkedin_scraper"
    
    @property
    def description(self) -> str:
        return "Scrapes LinkedIn profiles and saves them as JSON files"
    
    def scrape_profile(self, profile_id: str) -> dict:
        """Scrape a single profile by public ID or URN"""
        try:
            profile = self.client.get_profile(public_id=profile_id)
            return profile
        except Exception as e:
            logger.error(f"Failed to scrape profile {profile_id}: {e}")
            return {}
    
    def run(self, profile_ids: Optional[List[str]] = None, **kwargs):
        """
        Run the LinkedIn scraping job
        
        Args:
            profile_ids: List of LinkedIn profile IDs or URNs to scrape
                        If None, you should pass them as command line args
        """
        if not profile_ids:
            # For testing, use a default profile if none provided
            profile_ids = ["maxime-fournes-6b83b845"]
        
        results = {}
        for profile_id in profile_ids:
            logger.info(f"Scraping profile: {profile_id}")
            profile_data = self.scrape_profile(profile_id)
            if profile_data:
                results[profile_id] = profile_data
        
        if results:
            self.save_json_output(results, "linkedin_profiles")
            logger.info(f"Successfully scraped {len(results)} profiles")
        else:
            logger.warning("No profiles were successfully scraped")
        
        return results

if __name__ == "__main__":
    # Example usage
    scraper = LinkedInScraper()
    scraper.run() 