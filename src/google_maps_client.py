import googlemaps
import os
from typing import List, Dict, Optional
from google.genai.types import FunctionDeclaration, Schema, Type, Tool

class GoogleMapsClient:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLEMAP_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLEMAP_API_KEY not found in environment variables")
        self.client = googlemaps.Client(key=self.api_key)

    def search_places(self, query: str, location: str = None) -> tuple[str, list]:
        """
        Search for places based on a query.
        Returns a formatted string with place recommendations.
        """
        try:
            # Default location: Kyobashi Station, Osaka
            default_location = (34.6977, 135.5357)
            
            # simple text search with Japanese language
            places_result = self.client.places(
                query=query,
                language='ja',
                location=default_location,
                radius=5000
            )
            
            if not places_result.get('results'):
                return "すみません、その場所は見つかりませんでした。", []

            results = places_result['results'][:3] # Top 3
            response = "以下の場所が見つかりました：\n"
            
            structured_results = []
            for place in results:
                name = place.get('name')
                address = place.get('formatted_address')
                rating = place.get('rating', 'N/A')
                response += f"- {name} (評価: {rating}) - {address}\n"
                structured_results.append({
                    "name": name,
                    "address": address,
                    "rating": rating,
                    "place_id": place.get('place_id'),
                    "geometry": place.get('geometry')
                })
            
            return response, structured_results

        except Exception as e:
            print(f"Google Maps API Error: {e}")
            return "Google Maps API Error: Google Mapsでの検索中にエラーが発生しました。", []

def get_tool_declaration() -> Tool:
    return Tool(function_declarations=[
        FunctionDeclaration(
            name="searchPlaces",
            description="Search for places and get recommendations using Google Maps.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "query": Schema(
                        type=Type.STRING,
                        description="The search query (e.g., 'restaurants nearby', 'gas station')."
                    ),
                    "location": Schema(
                        type=Type.STRING,
                        description="Optional location to bias the search."
                    )
                },
                required=["query"]
            )
        )
    ])
