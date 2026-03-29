"""
Video Search Module

This module handles searching for exercise videos and formatting them for display.
Uses Tavily API for search.
"""

import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
try:
    from tavily import TavilyClient
except ImportError:
    logger.warning("⚠️ Tavily not installed. Install with: pip install tavily-python")
    logger.warning("   Video references will be disabled without Tavily API key")
    TavilyClient = None


def search_exercise_videos(query: str, max_results: int = 3) -> list:
    """
    Search for exercise/fitness videos using Tavily Search API
    """
    if not TavilyClient:
        return []
    
    try:
        # Initialize Tavily client
        tavily = TavilyClient(api_key=os.getenv('TAVILY_API_KEY'))
        
        # Search with YouTube focus for exercise videos
        search_query = f"{query} exercise workout tutorial YouTube video"
        
        response = tavily.search(
            query=search_query,
            search_depth="basic",
            max_results=max_results,
            include_domains=["youtube.com"]
        )
        
        # Filter for YouTube results
        video_links = []
        for result in response.get('results', []):
            if 'youtube.com' in result.get('url', ''):
                video_links.append({
                    'title': result.get('title', 'No title'),
                    'url': result.get('url'),
                    'description': result.get('content', 'No description'),
                    'score': result.get('score', 0)
                })
        
        return video_links
        
    except Exception as e:
        logger.error("⚠️ Error searching for videos: %s", e)
        return []


def format_video_references(videos: list) -> str:
    """
    Format video references for display in WhatsApp messages.
    Uses WhatsApp-compatible formatting (*text* for bold).
    """
    if not videos:
        return ""
    
    video_text = "\n\n🎥 *Helpful Video References:*\n"
    for i, video in enumerate(videos[:2], 1):  # Limit to top 2 videos for WhatsApp
        video_text += f"{i}. *{video['title']}*\n"
        video_text += f"   🔗 {video['url']}\n"
        if video['description'] and len(video['description']) > 50:
            video_text += f"   📝 {video['description'][:80]}...\n"
        video_text += "\n"
    
    return video_text


if __name__ == "__main__":
    # Test the search_exercise_videos function
    test_query = "push up exercise"
    logger.info("Testing video search for: '%s'", test_query)

    videos = search_exercise_videos(test_query, max_results=2)

    if videos:
        logger.info("✅ API is working! Found videos:")
        for video in videos:
            logger.info("Title: %s", video['title'])
            logger.info("URL: %s", video['url'])
            logger.info("Description: %s...", video['description'][:100])
    else:
        logger.error("❌ No videos found or API not working. Check your TAVILY_API_KEY and internet connection.")