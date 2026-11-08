"""Download a curated USDA FoodData Central reference cache.

The cache is attribution data for ingredients. Pakistani cooked dishes are
calculated later from these values and are labelled recipe estimates.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.nal.usda.gov/fdc/v1/foods/search"
OUT = Path(__file__).resolve().parents[1] / "seeds" / "data" / "usda_reference.json"
QUERIES = [
    "rice raw", "brown rice raw", "wheat flour", "whole wheat flour", "semolina",
    "corn flour", "chickpea flour", "rice flour", "bread white", "oats",
    "milk whole", "milk reduced fat", "milk powder", "yogurt plain", "greek yogurt",
    "butter", "ghee", "cream", "paneer", "cheddar cheese", "mozzarella",
    "egg whole raw", "egg white raw", "egg yolk raw", "chicken breast raw",
    "chicken thigh raw", "chicken liver raw", "beef raw", "beef liver", "lamb raw",
    "goat raw", "fish raw", "salmon raw", "tuna raw", "shrimp raw", "prawns raw",
    "onion raw", "tomato raw", "potato raw", "sweet potato raw", "spinach raw",
    "cauliflower raw", "cabbage raw", "carrot raw", "peas raw", "okra raw",
    "eggplant raw", "pumpkin raw", "cucumber raw", "radish raw", "turnip raw",
    "bitter gourd", "bottle gourd", "green beans", "bell pepper", "chili pepper raw",
    "garlic raw", "ginger raw", "coriander raw", "mint raw", "fenugreek leaves",
    "mustard greens", "lettuce raw", "broccoli raw", "mushroom raw", "corn raw",
    "beet raw", "zucchini raw", "lemon raw", "lime raw", "lentils raw",
    "chickpeas raw", "kidney beans raw", "mung beans raw", "black gram",
    "split peas", "soybeans raw", "tofu", "oil vegetable", "olive oil",
    "mustard oil", "coconut oil", "sunflower oil", "canola oil", "sugar",
    "honey", "salt", "cumin seed", "coriander seed", "turmeric", "black pepper",
    "cardamom", "cinnamon", "clove", "red chili powder", "fenugreek seed",
    "fennel seed", "nigella seed", "bay leaf", "banana raw", "mango raw",
    "apple raw", "orange raw", "dates", "guava raw", "papaya raw", "watermelon raw",
    "grapes raw", "pomegranate raw", "peach raw", "plum raw", "apricot raw",
    "fig raw", "strawberries", "melon", "pineapple raw", "almonds", "peanuts",
    "walnuts", "cashews", "pistachios", "sesame seeds", "sunflower seeds",
    "flaxseed", "chia seeds", "raisins", "coconut", "tea brewed", "coffee brewed",
    "orange juice", "apple juice", "cola", "ice cream vanilla", "condensed milk",
    "vermicelli", "popcorn", "potato chips", "mayonnaise", "ketchup", "vinegar",
    "soy sauce", "yogurt drink", "buttermilk", "whey", "beef suet", "tripe beef",
    "beef brain", "chicken giblets", "sardines", "mackerel raw", "cod raw",
    "tilapia raw", "crab raw", "lobster", "wheat bread", "pita bread", "tortilla",
    "rice cooked", "pasta cooked", "noodles", "barley", "millet", "sorghum",
    "quinoa", "bulgur", "couscous", "black beans", "pinto beans", "navy beans",
    "white beans", "urad", "masoor", "allspice", "nutmeg", "paprika", "saffron",
    "tamarind", "jaggery", "molasses", "cocoa", "dark chocolate", "milk chocolate",
    "biscuit", "cake plain", "doughnut", "samosa", "naan", "paratha",
]

KEEP = ("Energy", "Protein", "Carbohydrate, by difference", "Total lipid (fat)",
        "Fiber, total dietary", "Sugars, total including NLEA", "Sugars, total",
        "Sodium, Na", "Fatty acids, total saturated")
SKIP = ("baby food", "infant", "alcoholic", "wine", "beer", "whisky", "whiskey",
        "liqueur", "mcdonald", "burger king", "wendy", "kfc", "pizza hut")


def extract(food: dict) -> dict | None:
    description = food.get("description") or ""
    low = description.lower()
    if any(word in low for word in SKIP):
        return None
    nutrients = {}
    for item in food.get("foodNutrients") or []:
        name = item.get("nutrientName")
        if name not in KEEP:
            continue
        unit = (item.get("unitName") or "").upper()
        if name == "Energy" and unit not in {"KCAL", "KCAL"}:
            if unit != "KCAL":
                continue
        nutrients[name] = item.get("value")
    kcal = nutrients.get("Energy")
    if kcal is None:
        return None
    return {
        "fdc_id": food.get("fdcId"),
        "description": description,
        "data_type": food.get("dataType"),
        "food_category": food.get("foodCategory"),
        "energy_kcal": kcal,
        "protein_g": nutrients.get("Protein"),
        "carbohydrate_g": nutrients.get("Carbohydrate, by difference"),
        "fat_g": nutrients.get("Total lipid (fat)"),
        "saturated_fat_g": nutrients.get("Fatty acids, total saturated"),
        "fibre_g": nutrients.get("Fiber, total dietary"),
        "sugar_g": nutrients.get("Sugars, total including NLEA", nutrients.get("Sugars, total")),
        "sodium_mg": nutrients.get("Sodium, Na"),
        "published": food.get("publishedDate"),
    }


def main() -> None:
    key = "DEMO_KEY"
    found: dict[int, dict] = {}
    for index, query in enumerate(QUERIES, start=1):
        params = urllib.parse.urlencode({
            "api_key": key,
            "query": query,
            "pageSize": 15,
            "dataType": "SR Legacy,Foundation",
        })
        url = f"{API}?{params}"
        try:
            with urllib.request.urlopen(url, timeout=40) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 - importer should continue
            print(f"skip {query}: {exc}")
            time.sleep(1)
            continue
        added = 0
        for food in payload.get("foods") or []:
            parsed = extract(food)
            if not parsed or parsed["fdc_id"] in found:
                continue
            found[parsed["fdc_id"]] = parsed
            added += 1
        print(f"{index}/{len(QUERIES)} {query}: +{added} total {len(found)}")
        time.sleep(0.35)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    records = sorted(found.values(), key=lambda item: item["description"].lower())
    OUT.write_text(json.dumps({
        "source": "USDA FoodData Central",
        "source_url": "https://fdc.nal.usda.gov/",
        "licence_note": "USDA FoodData Central data is US public domain. Preserve fdc_id attribution.",
        "fetched_with": "DEMO_KEY",
        "count": len(records),
        "foods": records,
    }, indent=2), encoding="utf-8")
    print(f"wrote {len(records)} to {OUT}")


if __name__ == "__main__":
    main()
