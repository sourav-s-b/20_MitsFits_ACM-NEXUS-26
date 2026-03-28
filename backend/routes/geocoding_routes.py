from fastapi import APIRouter
import os
import requests
from dotenv import load_dotenv

router = APIRouter()
load_dotenv()

TOMTOM_KEY = os.getenv("TOMTOM_API_KEY")

@router.get("/geocoding/search")
def search_address(query: str):
    """
    Search for a location using TomTom Search API.
    Returns lat, lon and description.
    """
    if not query:
        return []
    
    url = (
        f"https://api.tomtom.com/search/2/geocode/{query}.json"
        f"?key={TOMTOM_KEY}&limit=5&language=en-US"
    )
    
    try:
        resp = requests.get(url, timeout=5).json()
        results = resp.get("results", [])
        
        formatted = []
        for r in results:
            formatted.append({
                "label": r["address"]["freeformAddress"],
                "lat":   r["position"]["lat"],
                "lon":   r["position"]["lon"]
            })
        return formatted
    except Exception as e:
        print(f"Geocoding Error: {e}")
        return []
