from strands import tool
from pydantic import BaseModel, Field
from typing import Literal


class RestaurantInput(BaseModel):
    city: str = Field(description="The city to search for restaurants in")
    fine_dining: Literal["Yes", "No"] = Field(
        description="Whether the user wants fine dining. 'Yes' for fine dining, 'No' for casual."
    )


MOCK_RESTAURANTS = {
    "tokyo": {
        "Yes": [
            {"name": "Narisawa", "cuisine": "Innovative Japanese", "price_range": "$$$$"},
            {"name": "Ryugin", "cuisine": "Kaiseki", "price_range": "$$$$"},
            {"name": "Quintessence", "cuisine": "French-Japanese", "price_range": "$$$$"},
        ],
        "No": [
            {"name": "Ichiran Ramen", "cuisine": "Ramen", "price_range": "$"},
            {"name": "Gonpachi", "cuisine": "Izakaya", "price_range": "$$"},
            {"name": "Uobei Shibuya", "cuisine": "Conveyor Belt Sushi", "price_range": "$"},
        ],
    },
    "paris": {
        "Yes": [
            {"name": "Guy Savoy", "cuisine": "French Haute Cuisine", "price_range": "$$$$"},
            {"name": "Arpège", "cuisine": "Vegetable-Focused French", "price_range": "$$$$"},
            {"name": "Le Cinq", "cuisine": "Classic French", "price_range": "$$$$"},
        ],
        "No": [
            {"name": "L'As du Fallafel", "cuisine": "Middle Eastern", "price_range": "$"},
            {"name": "Breizh Café", "cuisine": "Crêperie", "price_range": "$$"},
            {"name": "Bouillon Pigalle", "cuisine": "Traditional French Bistro", "price_range": "$$"},
        ],
    },
    "new york": {
        "Yes": [
            {"name": "Per Se", "cuisine": "New American", "price_range": "$$$$"},
            {"name": "Le Bernardin", "cuisine": "Seafood", "price_range": "$$$$"},
            {"name": "Eleven Madison Park", "cuisine": "Contemporary American", "price_range": "$$$$"},
        ],
        "No": [
            {"name": "Joe's Pizza", "cuisine": "Pizza", "price_range": "$"},
            {"name": "Katz's Delicatessen", "cuisine": "Deli", "price_range": "$$"},
            {"name": "Shake Shack", "cuisine": "Burgers", "price_range": "$"},
        ],
    },
}


@tool
def restaurant_collaborator(city: str, fine_dining: str) -> str:
    """Search for restaurants in a given city, optionally filtered by fine dining preference.

    Call this ONLY after you have confirmed both 'city' and 'fineDining' with the user.

    Args:
        city: The city to search for restaurants in.
        fine_dining: Whether the user wants fine dining. 'Yes' or 'No'.
    """
    city_lower = city.lower().strip()
    city_data = MOCK_RESTAURANTS.get(city_lower)

    if not city_data:
        available = ", ".join(MOCK_RESTAURANTS.keys())
        return f'No restaurants found for "{city}". Available cities: {available}. Please ask the user to choose a different city.'

    restaurants = city_data.get(fine_dining, [])
    dining_type = "Fine Dining" if fine_dining == "Yes" else "Casual Dining"

    lines = [f"## {dining_type} Restaurants in {city}\n"]
    for r in restaurants:
        lines.append(f"- **{r['name']}** | {r['cuisine']} | {r['price_range']}")

    lines.append("\n_Provided by Restaurant Collaborator_")
    return "\n".join(lines)
