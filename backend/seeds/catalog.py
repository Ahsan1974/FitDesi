"""Build the FitDesi food catalogue from USDA references and calculated recipes.

Cooked dishes do not copy raw calories. Their per-100 g values come from
ingredient totals divided by the cooked weight.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

from app.services.calc import combine_ingredients

DATA_PATH = Path(__file__).resolve().parents[1] / "seeds" / "data" / "usda_reference.json"
USDA_URL = "https://fdc.nal.usda.gov/"

# Rounded public USDA-style values used only when a live reference row is absent.
FALLBACK = {
    "chicken breast raw": (120, 22.5, 0, 2.62, 0, 0, 45, False),
    "chicken thigh raw": (177, 24.8, 0, 8.2, 0, 0, 84, False),
    "beef raw": (217, 26.1, 0, 11.8, 0, 0, 59, False),
    "lamb raw": (206, 25.6, 0, 10.7, 0, 0, 66, False),
    "fish raw": (82, 17.8, 0, 0.7, 0, 0, 54, False),
    "shrimp raw": (85, 20.1, 0.2, 0.5, 0, 0, 119, False),
    "egg whole raw": (143, 12.6, 0.7, 9.5, 0, 0.4, 142, False),
    "egg white raw": (52, 10.9, 0.7, 0.2, 0, 0.7, 166, False),
    "rice raw": (365, 7.1, 80, 0.7, 1.3, 0.1, 5, True),
    "brown rice raw": (367, 7.5, 76, 2.7, 3.5, 0.7, 5, True),
    "whole wheat flour": (340, 13.2, 72, 2.5, 10.7, 0.4, 2, True),
    "wheat flour": (364, 10.3, 76.3, 1.0, 2.7, 0.3, 2, True),
    "chickpea flour": (387, 22.4, 57.8, 6.7, 10.8, 10.8, 64, True),
    "semolina": (360, 12.7, 72.8, 1.1, 3.9, 0, 1, True),
    "corn flour": (361, 6.9, 76.9, 3.9, 7.3, 0.6, 5, True),
    "oats": (389, 16.9, 66.3, 6.9, 10.6, 0, 2, True),
    "bread white": (265, 9, 49, 3.2, 2.7, 5, 491, True),
    "milk whole": (61, 3.2, 4.8, 3.3, 0, 5.1, 43, False),
    "yogurt plain": (61, 3.5, 4.7, 3.3, 0, 4.7, 46, False),
    "greek yogurt": (97, 9.0, 3.9, 5.0, 0, 3.6, 35, False),
    "butter": (717, 0.9, 0.1, 81.1, 0, 0.1, 11, False),
    "ghee": (876, 0.3, 0, 99.5, 0, 0, 2, False),
    "cream": (340, 2.1, 2.8, 36, 0, 2.9, 38, False),
    "paneer": (265, 18.3, 1.2, 20.8, 0, 1.2, 18, False),
    "cheddar cheese": (403, 24.9, 1.3, 33.1, 0, 0.5, 621, False),
    "oil vegetable": (884, 0, 0, 100, 0, 0, 0, True),
    "olive oil": (884, 0, 0, 100, 0, 0, 2, True),
    "mustard oil": (884, 0, 0, 100, 0, 0, 0, True),
    "onion raw": (40, 1.1, 9.3, 0.1, 1.7, 4.2, 4, True),
    "tomato raw": (18, 0.9, 3.9, 0.2, 1.2, 2.6, 5, True),
    "potato raw": (77, 2.0, 17.5, 0.1, 2.1, 0.8, 6, True),
    "spinach raw": (23, 2.9, 3.6, 0.4, 2.2, 0.4, 79, True),
    "cauliflower raw": (25, 1.9, 5.0, 0.3, 2.0, 1.9, 30, True),
    "okra raw": (33, 1.9, 7.5, 0.2, 3.2, 1.5, 7, True),
    "eggplant raw": (25, 1.0, 5.9, 0.2, 3.0, 3.5, 2, True),
    "carrot raw": (41, 0.9, 9.6, 0.2, 2.8, 4.7, 69, True),
    "peas raw": (81, 5.4, 14.5, 0.4, 5.7, 5.7, 5, True),
    "cabbage raw": (25, 1.3, 5.8, 0.1, 2.5, 3.2, 18, True),
    "pumpkin raw": (26, 1.0, 6.5, 0.1, 0.5, 2.8, 1, True),
    "cucumber raw": (15, 0.7, 3.6, 0.1, 0.5, 1.7, 2, True),
    "turnip raw": (28, 0.9, 6.4, 0.1, 1.8, 3.8, 67, True),
    "radish raw": (16, 0.7, 3.4, 0.1, 1.6, 1.9, 39, True),
    "bitter gourd": (17, 1.0, 3.7, 0.2, 2.8, 1.9, 5, True),
    "bottle gourd": (14, 0.6, 3.4, 0.0, 0.5, 1.8, 2, True),
    "bell pepper": (20, 0.9, 4.6, 0.2, 1.7, 2.4, 4, True),
    "chili pepper raw": (40, 1.9, 8.8, 0.4, 1.5, 5.3, 7, True),
    "garlic raw": (149, 6.4, 33.1, 0.5, 2.1, 1.0, 17, True),
    "ginger raw": (80, 1.8, 17.8, 0.8, 2.0, 1.7, 13, True),
    "coriander raw": (23, 2.1, 3.7, 0.5, 2.8, 0.9, 46, True),
    "mint raw": (44, 3.3, 8.4, 0.7, 6.8, 0, 30, True),
    "fenugreek leaves": (49, 4.4, 6.0, 0.9, 1.1, 0, 67, True),
    "mustard greens": (27, 2.9, 4.7, 0.4, 3.2, 1.3, 20, True),
    "green beans": (31, 1.8, 7.0, 0.2, 2.7, 3.3, 6, True),
    "mushroom raw": (22, 3.1, 3.3, 0.3, 1.0, 2.0, 5, True),
    "corn raw": (86, 3.3, 18.7, 1.4, 2.0, 6.3, 15, True),
    "beet raw": (43, 1.6, 9.6, 0.2, 2.8, 6.8, 78, True),
    "sweet potato raw": (86, 1.6, 20.1, 0.1, 3.0, 4.2, 55, True),
    "lemon raw": (29, 1.1, 9.3, 0.3, 2.8, 2.5, 2, True),
    "lentils raw": (352, 24.6, 63.4, 1.1, 10.7, 2.0, 6, True),
    "chickpeas raw": (378, 20.5, 63, 6.0, 12.2, 10.7, 24, True),
    "kidney beans raw": (333, 23.6, 60, 0.8, 15.2, 2.2, 24, True),
    "mung beans raw": (347, 23.9, 62.6, 1.2, 16.3, 6.6, 15, True),
    "black gram": (341, 25.2, 59, 1.6, 18.3, 0, 38, True),
    "sugar": (387, 0, 100, 0, 0, 100, 1, True),
    "honey": (304, 0.3, 82.4, 0, 0.2, 82.1, 4, False),
    "salt": (0, 0, 0, 0, 0, 0, 38758, True),
    "cumin seed": (375, 17.8, 44.2, 22.3, 10.5, 2.3, 168, True),
    "coriander seed": (298, 12.4, 55, 17.8, 41.9, 0, 35, True),
    "turmeric": (312, 9.7, 67.1, 3.3, 22.7, 3.2, 27, True),
    "black pepper": (251, 10.4, 64, 3.3, 25.3, 0.6, 20, True),
    "red chili powder": (282, 13.5, 49.7, 14.3, 34.8, 7.2, 2860, True),
    "cardamom": (311, 10.8, 68.5, 6.7, 28, 0, 18, True),
    "cinnamon": (247, 4.0, 80.6, 1.2, 53.1, 2.2, 10, True),
    "clove": (274, 6.0, 65.5, 13, 33.9, 2.4, 277, True),
    "fennel seed": (345, 15.8, 52.3, 14.9, 39.8, 0, 88, True),
    "garam masala": (325, 12, 48, 12, 20, 4, 80, True),
    "banana raw": (89, 1.1, 22.8, 0.3, 2.6, 12.2, 1, True),
    "mango raw": (60, 0.8, 15, 0.4, 1.6, 13.7, 1, True),
    "apple raw": (52, 0.3, 13.8, 0.2, 2.4, 10.4, 1, True),
    "orange raw": (47, 0.9, 11.8, 0.1, 2.4, 9.4, 0, True),
    "dates": (277, 1.8, 75, 0.2, 6.7, 66.5, 1, True),
    "guava raw": (68, 2.6, 14.3, 1.0, 5.4, 8.9, 2, True),
    "papaya raw": (43, 0.5, 10.8, 0.3, 1.7, 7.8, 8, True),
    "watermelon raw": (30, 0.6, 7.6, 0.2, 0.4, 6.2, 1, True),
    "grapes raw": (69, 0.7, 18.1, 0.2, 0.9, 15.5, 2, True),
    "pomegranate raw": (83, 1.7, 18.7, 1.2, 4.0, 13.7, 3, True),
    "almonds": (579, 21.2, 21.6, 49.9, 12.5, 4.4, 1, True),
    "peanuts": (567, 25.8, 16.1, 49.2, 8.5, 4.7, 18, True),
    "walnuts": (654, 15.2, 13.7, 65.2, 6.7, 2.6, 2, True),
    "cashews": (553, 18.2, 30.2, 43.9, 3.3, 5.9, 12, True),
    "sesame seeds": (573, 17.7, 23.4, 49.7, 11.8, 0.3, 11, True),
    "raisins": (299, 3.1, 79.2, 0.5, 3.7, 59.2, 11, True),
    "coconut": (354, 3.3, 15.2, 33.5, 9.0, 6.2, 20, True),
    "tamarind": (239, 2.8, 62.5, 0.6, 5.1, 38.8, 28, True),
    "jaggery": (383, 0.4, 98, 0.1, 0, 95, 30, True),
    "water": (0, 0, 0, 0, 0, 0, 0, True),
    "tea brewed": (1, 0, 0.3, 0, 0, 0, 3, True),
    "coffee brewed": (1, 0.1, 0, 0, 0, 0, 2, True),
    "orange juice": (45, 0.7, 10.4, 0.2, 0.2, 8.4, 1, True),
    "cola": (41, 0, 10.6, 0, 0, 10.6, 4, True),
    "condensed milk": (321, 7.9, 54.4, 8.7, 0, 54.4, 127, False),
    "milk powder": (496, 26.3, 38.4, 26.7, 0, 38.4, 371, False),
    "vermicelli": (368, 12, 75, 1.5, 3, 2, 10, True),
    "mayonnaise": (680, 1, 0.6, 75, 0, 0.6, 635, False),
    "ketchup": (112, 1.0, 26, 0.3, 0.3, 22, 907, True),
    "vinegar": (21, 0, 0.9, 0, 0, 0.4, 2, True),
    "ice cream vanilla": (207, 3.5, 23.6, 11, 0.7, 21.2, 80, False),
    "soya chunks": (345, 52, 33, 0.5, 13, 0, 10, True),
    "tofu": (76, 8, 1.9, 4.8, 0.3, 0.6, 7, True),
    "beef liver": (135, 20.4, 3.9, 3.6, 0, 0, 69, False),
    "chicken liver raw": (119, 16.9, 0.7, 4.8, 0, 0, 71, False),
    "tripe beef": (85, 12.1, 0, 3.7, 0, 0, 97, False),
    "beef brain": (143, 10.9, 1.1, 10.3, 0, 0, 126, False),
}

URDU = {
    "chicken": "چکن", "beef": "بیف", "mutton": "مٹن", "fish": "فش", "prawn": "جھینگا",
    "biryani": "بریانی", "pulao": "پلاؤ", "karahi": "کڑاہی", "korma": "قورمہ",
    "nihari": "نہاری", "haleem": "حلیم", "daal": "دال", "dal": "دال", "roti": "روٹی",
    "paratha": "پراٹھا", "naan": "نان", "chai": "چائے", "lassi": "لسی", "aloo": "آلو",
    "palak": "پالک", "gobi": "گوبھی", "bhindi": "بھنڈی", "baingan": "بینگن",
    "keema": "قیمہ", "kebab": "کباب", "tikka": "تکہ", "halwa": "حلوا", "kheer": "کھیر",
    "samosa": "سموسہ", "pakora": "پکوڑا", "chapati": "چپاتی", "rice": "چاول",
    "yogurt": "دہی", "egg": "انڈا", "omelette": "آملیٹ", "salad": "سلاد",
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:170] or "food"


def profile_from_tuple(row: tuple) -> dict:
    kcal, protein, carb, fat, fibre, sugar, sodium, _veg = row
    return {
        "energy_kcal": kcal,
        "protein_g": protein,
        "carbohydrate_g": carb,
        "fat_g": fat,
        "saturated_fat_g": None,
        "fibre_g": fibre,
        "sugar_g": sugar,
        "sodium_mg": sodium,
    }


def load_usda() -> list[dict]:
    if not DATA_PATH.exists():
        return []
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    foods = []
    for row in payload.get("foods", []):
        if row.get("energy_kcal") is None:
            continue
        foods.append(row)
    return foods


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def match_reference(query: str, usda: list[dict]) -> dict | None:
    tokens = [token for token in _norm(query).split() if token]
    best = None
    best_score = -999
    for row in usda:
        words = _norm(row["description"]).split()
        word_set = set(words)
        if not tokens or not all(token in word_set for token in tokens):
            continue
        score = 8
        if words and words[0] == tokens[0]:
            score += 6
        if "raw" in word_set:
            score += 3
        if any(word in word_set for word in ("fried", "breaded", "candied", "baby")):
            score -= 8
        score -= max(len(words) - len(tokens), 0) * 0.8
        if score > best_score:
            best_score = score
            best = row
    if best is None or best_score < 6:
        return None
    return best


def ingredient_profile(query: str, usda: list[dict]) -> tuple[dict, dict]:
    matched = match_reference(query, usda)
    if matched:
        profile = {
            "energy_kcal": matched.get("energy_kcal"),
            "protein_g": matched.get("protein_g"),
            "carbohydrate_g": matched.get("carbohydrate_g"),
            "fat_g": matched.get("fat_g"),
            "saturated_fat_g": matched.get("saturated_fat_g"),
            "fibre_g": matched.get("fibre_g"),
            "sugar_g": matched.get("sugar_g"),
            "sodium_mg": matched.get("sodium_mg"),
        }
        source = {
            "source_name": "USDA FoodData Central",
            "source_id": str(matched.get("fdc_id")),
            "source_url": USDA_URL,
            "licence": "US public domain",
            "attribution": matched.get("description"),
            "quality": "imported",
        }
        return profile, source
    if query not in FALLBACK:
        raise KeyError(query)
    source = {
        "source_name": "Compiled rounded reference used because no USDA row matched",
        "source_id": None,
        "source_url": USDA_URL,
        "licence": "Values are rounded published-style references, not a new laboratory assay",
        "attribution": query,
        "quality": "compiled_reference",
    }
    return profile_from_tuple(FALLBACK[query]), source


def urdu_name(english: str) -> str:
    parts = []
    for word in re.split(r"[^A-Za-z]+", english.lower()):
        if word in URDU:
            parts.append(URDU[word])
    return " ".join(parts)


def _food_shell(**kwargs) -> dict:
    base = {
        "aliases": [],
        "name_ur": "",
        "name_roman": "",
        "subcategory": None,
        "cuisine": "pakistani",
        "kind": "dish",
        "preparation": "cooked",
        "is_vegetarian": False,
        "is_vegan": False,
        "default_serving_label": "100 g",
        "default_serving_g": 100,
        "servings": [{"label": "100 g", "grams": 100, "unit_kind": "weight", "source_note": "Standard weight"}],
        "data_origin": "recipe_estimate",
        "verification_status": "awaiting_verification",
        "data_confidence": "medium",
        "nutrition_note": "Estimated from ingredients and a cooked weight. It is not a laboratory analysis.",
        "image_url": None,
        "method": None,
        "instructions": None,
        "ingredients": [],
        "raw_weight_g": None,
        "cooked_weight_g": None,
        "added_water_g": 0,
        "water_loss_g": 0,
    }
    base.update(kwargs)
    if not base["name_ur"]:
        base["name_ur"] = urdu_name(base["name_en"])
    if not base["name_roman"]:
        base["name_roman"] = base["name_en"].lower()
    base["slug"] = slugify(base["slug"] if base.get("slug") else base["name_en"])
    return base


def _cook(query_items: list[tuple[str, float]], usda: list[dict], added_water_g: float, water_loss_g: float) -> tuple[dict, list[dict]]:
    resolved = []
    profiles = []
    for query, grams in query_items:
        profile, source = ingredient_profile(query, usda)
        profiles.append((profile, grams))
        resolved.append({"query": query, "grams": grams, "source": source, "profile": profile})
    cooked = combine_ingredients(profiles, added_water_g=added_water_g, water_loss_g=water_loss_g)
    return cooked, resolved


def build_catalog() -> dict:
    usda = load_usda()
    foods: dict[str, dict] = {}
    warnings: list[str] = []

    def add(record: dict) -> None:
        slug = record["slug"]
        if slug in foods:
            warnings.append(f"Duplicate slug skipped: {slug}")
            return
        record["search_text"] = " ".join(
            [record["name_en"], record.get("name_ur") or "", record.get("name_roman") or "", *record.get("aliases", [])]
        ).lower()
        foods[slug] = record

    for row in usda:
        name = row["description"]
        vegan = "meat" not in name.lower() and "chicken" not in name.lower() and "beef" not in name.lower()
        add(_food_shell(
            slug=f"usda-{row['fdc_id']}",
            name_en=name,
            name_roman=name.lower(),
            category="ingredients",
            cuisine="general",
            kind="ingredient",
            preparation="raw" if "raw" in name.lower() else "cooked",
            is_vegetarian=vegan or "egg" not in name.lower(),
            is_vegan=False,
            data_origin="imported_usda",
            data_confidence="high",
            nutrition_note="Copied from USDA FoodData Central. Review before clinical use.",
            per_100g={
                "energy_kcal": row.get("energy_kcal"),
                "protein_g": row.get("protein_g"),
                "carbohydrate_g": row.get("carbohydrate_g"),
                "fat_g": row.get("fat_g"),
                "saturated_fat_g": row.get("saturated_fat_g"),
                "fibre_g": row.get("fibre_g"),
                "sugar_g": row.get("sugar_g"),
                "sodium_mg": row.get("sodium_mg"),
            },
            source={
                "source_name": "USDA FoodData Central",
                "source_id": str(row.get("fdc_id")),
                "source_url": USDA_URL,
                "licence": "US public domain",
                "attribution": name,
                "quality": row.get("data_type") or "imported",
            },
        ))

    for key, row in FALLBACK.items():
        slug = slugify(key)
        if slug in foods:
            continue
        _kcal, _p, _c, _f, _fi, _s, _na, veg = row
        add(_food_shell(
            slug=slug,
            name_en=key.title(),
            category="ingredients",
            cuisine="general",
            kind="ingredient",
            preparation="raw",
            is_vegetarian=True,
            is_vegan=veg,
            data_origin="compiled_reference",
            data_confidence="medium",
            nutrition_note="Rounded reference used for recipe calculation when a USDA row is not matched. Awaiting verification.",
            per_100g=profile_from_tuple(row),
            source={
                "source_name": "Compiled rounded reference",
                "source_id": None,
                "source_url": USDA_URL,
                "licence": "Not a substitute for the original tables",
                "attribution": "Rounded from widely published food-composition values",
                "quality": "compiled_reference",
            },
        ))

    for recipe in recipe_definitions():
        cooked, resolved = _cook(recipe["ingredients"], usda, recipe.get("added_water_g", 0), recipe.get("water_loss_g", 0))
        vegan = all(FALLBACK.get(item["query"], (0, 0, 0, 0, 0, 0, 0, True))[7] for item in resolved)
        vegetarian = vegan or all(
            item["query"] not in {"chicken breast raw", "chicken thigh raw", "beef raw", "lamb raw", "fish raw", "shrimp raw", "beef liver", "chicken liver raw", "tripe beef", "beef brain"}
            for item in resolved
        )
        servings = [{"label": "100 g", "grams": 100, "unit_kind": "weight", "source_note": "Standard weight"}]
        for label, grams in recipe.get("servings", []):
            servings.append({"label": label, "grams": grams, "unit_kind": "household", "source_note": recipe.get("serving_note", "Household portion for this recipe yield")})
        note = recipe.get("note") or "Estimated from the ingredient weights and the stated cooked yield. Hidden oil and restaurant portions can differ."
        add(_food_shell(
            slug=recipe["slug"],
            name_en=recipe["name_en"],
            name_ur=recipe.get("name_ur") or "",
            name_roman=recipe.get("name_roman") or recipe["name_en"].lower(),
            aliases=recipe.get("aliases", []),
            category=recipe["category"],
            subcategory=recipe.get("subcategory"),
            cuisine=recipe.get("cuisine", "pakistani"),
            kind="dish",
            preparation="cooked",
            is_vegetarian=recipe.get("vegetarian", vegetarian),
            is_vegan=recipe.get("vegan", vegan and vegetarian),
            default_serving_label=servings[-1]["label"] if len(servings) > 1 else "100 g",
            default_serving_g=servings[-1]["grams"] if len(servings) > 1 else 100,
            servings=servings,
            data_origin="recipe_estimate",
            data_confidence=recipe.get("confidence", "medium"),
            nutrition_note=note,
            per_100g=cooked["per_100g"],
            ingredients=[{"query": item["query"], "grams": item["grams"], "fdc_id": item["source"].get("source_id")} for item in resolved],
            raw_weight_g=cooked["raw_weight_g"],
            cooked_weight_g=cooked["cooked_weight_g"],
            added_water_g=cooked["added_water_g"],
            water_loss_g=cooked["water_loss_g"],
            method=recipe.get("method"),
            instructions=recipe.get("instructions"),
            source={
                "source_name": "FitDesi recipe calculation",
                "source_id": recipe["slug"],
                "source_url": None,
                "licence": "Calculated estimate",
                "attribution": "Ingredient values traced to USDA FoodData Central or a compiled rounded reference",
                "quality": "recipe_estimate",
            },
        ))

    records = list(foods.values())
    return {"foods": records, "warnings": warnings, "stats": coverage(records)}


def coverage(foods: list[dict]) -> dict:
    def count(origin: str) -> int:
        return sum(1 for food in foods if food["data_origin"] == origin)

    by_cuisine: dict[str, int] = {}
    for food in foods:
        by_cuisine[food.get("cuisine") or "unspecified"] = by_cuisine.get(food.get("cuisine") or "unspecified", 0) + 1
    return {
        "total": len(foods),
        "verified": sum(1 for food in foods if food["verification_status"] == "verified"),
        "awaiting_verification": sum(1 for food in foods if food["verification_status"] != "verified"),
        "imported_usda": count("imported_usda"),
        "compiled_reference": count("compiled_reference"),
        "recipe_estimate": count("recipe_estimate"),
        "ingredients": sum(1 for food in foods if food["kind"] == "ingredient"),
        "recipes": count("recipe_estimate"),
        "by_cuisine": by_cuisine,
    }


def _piece(name, ur, roman, category, cuisine, ingredients, water, loss, servings, **extra):
    slug = extra.pop("slug", slugify(name))
    return {
        "slug": slug,
        "name_en": name,
        "name_ur": ur,
        "name_roman": roman,
        "category": category,
        "cuisine": cuisine,
        "ingredients": ingredients,
        "added_water_g": water,
        "water_loss_g": loss,
        "servings": servings,
        **extra,
    }


def recipe_definitions() -> list[dict]:
    recipes: list[dict] = []
    oil = "oil vegetable"
    onion = "onion raw"
    tomato = "tomato raw"
    garlic = "garlic raw"
    ginger = "ginger raw"
    chili = "chili pepper raw"
    salt = "salt"
    turmeric = "turmeric"
    cumin = "cumin seed"
    yogurt = "yogurt plain"
    chicken = "chicken breast raw"
    beef = "beef raw"
    lamb = "lamb raw"
    rice = "rice raw"

    def spice(base: list[tuple[str, float]]) -> list[tuple[str, float]]:
        return [*base, (garlic, 6), (ginger, 6), (chili, 5), (salt, 2), (turmeric, 1), (cumin, 1), ("garam masala", 1)]

    famous = [
        _piece("Chicken Biryani", "چکن بریانی", "chicken biryani", "rice", "punjabi",
               spice([(chicken, 250), (rice, 160), (onion, 90), (tomato, 60), (yogurt, 70), (oil, 30)]),
               300, 70, [("1 plate", 380)], aliases=["biryani chicken", "chiken biryani", "briyani"],
               method="dum", subcategory="biryani"),
        _piece("Beef Biryani", "بیف بریانی", "beef biryani", "rice", "karachi",
               spice([(beef, 250), (rice, 160), (onion, 100), (tomato, 70), (yogurt, 60), (oil, 35), ("potato raw", 80)]),
               300, 80, [("1 plate", 400)], cuisine_ignored=None, method="dum"),
        _piece("Mutton Biryani", "مٹن بریانی", "mutton biryani", "rice", "punjabi",
               spice([(lamb, 260), (rice, 160), (onion, 100), (tomato, 50), (yogurt, 80), (oil, 35)]),
               300, 80, [("1 plate", 400)], method="dum"),
        _piece("Sindhi Biryani", "سندھی بریانی", "sindhi biryani", "rice", "sindhi",
               spice([(chicken, 240), (rice, 160), (onion, 80), (tomato, 100), (yogurt, 50), (oil, 30), ("potato raw", 100), ("tamarind", 8)]),
               280, 70, [("1 plate", 400)], method="dum"),
        _piece("Karachi Biryani", "کراچی بریانی", "karachi biryani", "rice", "karachi",
               spice([(chicken, 230), (rice, 170), (onion, 70), (tomato, 80), (yogurt, 40), (oil, 28), ("potato raw", 70)]),
               300, 60, [("1 plate", 380)], method="dum"),
        _piece("Bombay Biryani", "بمبئی بریانی", "bombay biryani", "rice", "karachi",
               spice([(chicken, 220), (rice, 160), (onion, 70), (tomato, 70), (yogurt, 40), (oil, 25), ("potato raw", 60)]),
               280, 60, [("1 plate", 360)], method="dum"),
        _piece("Hyderabadi Biryani", "حیدرآبادی بریانی", "hyderabadi biryani", "rice", "south_punjab",
               spice([(lamb, 250), (rice, 160), (onion, 120), (yogurt, 90), (oil, 40), ("mint raw", 8)]),
               280, 80, [("1 plate", 400)], method="dum"),
        _piece("Memoni Biryani", "میمون بریانی", "memoni biryani", "rice", "karachi",
               spice([(lamb, 240), (rice, 150), (onion, 100), (tomato, 80), (yogurt, 70), (oil, 35)]),
               260, 70, [("1 plate", 380)], method="dum"),
        _piece("Chicken Pulao", "چکن پلاؤ", "chicken pulao", "rice", "punjabi",
               spice([(chicken, 220), (rice, 170), (onion, 80), (yogurt, 40), (oil, 25)]),
               320, 60, [("1 plate", 360)], method="yakhni"),
        _piece("Beef Pulao", "بیف پلاؤ", "beef pulao", "rice", "punjabi",
               spice([(beef, 230), (rice, 170), (onion, 80), (oil, 28)]),
               320, 70, [("1 plate", 370)], method="yakhni"),
        _piece("Mutton Pulao", "مٹن پلاؤ", "mutton pulao", "rice", "punjabi",
               spice([(lamb, 240), (rice, 170), (onion, 90), (yogurt, 30), (oil, 30)]),
               320, 70, [("1 plate", 380)], method="yakhni"),
        _piece("Yakhni Pulao", "یخنی پلاؤ", "yakhni pulao", "rice", "punjabi",
               spice([(lamb, 200), (rice, 180), (onion, 70), (oil, 25)]),
               360, 80, [("1 plate", 360)], method="yakhni"),
        _piece("Kabuli Pulao", "کابلی پلاؤ", "kabuli pulao", "rice", "pashtun",
               spice([(lamb, 220), (rice, 180), (onion, 100), (oil, 30), ("carrot raw", 80), ("raisins", 15)]),
               300, 70, [("1 plate", 380)], method="steamed"),
        _piece("Vegetable Pulao", "ویجیٹبل پلاؤ", "vegetable pulao", "rice", "pakistani",
               [(rice, 160), (onion, 60), ("potato raw", 50), ("peas raw", 40), ("carrot raw", 40), (oil, 18), (salt, 2), (cumin, 1)],
               300, 50, [("1 plate", 320)], vegetarian=True, method="steamed"),
        _piece("Tahiri", "تحریر", "tahiri", "rice", "karachi",
               [(rice, 160), (onion, 50), ("potato raw", 70), (oil, 20), (salt, 2), (turmeric, 2), (cumin, 1)],
               300, 40, [("1 plate", 320)], vegetarian=True),
        _piece("Chicken Fried Rice", "چکن فرائیڈ رائس", "chicken fried rice", "rice", "pakistani",
               [(rice, 180), (chicken, 80), (onion, 30), ("peas raw", 30), ("carrot raw", 30), ("egg whole raw", 50), (oil, 15), (salt, 2)],
               20, 25, [("1 plate", 280)]),
        _piece("Daal Chawal", "دال چاول", "daal chawal", "rice", "punjabi",
               [("lentils raw", 70), (rice, 80), (onion, 30), (tomato, 30), (oil, 12), (salt, 2), (turmeric, 1), (cumin, 1)],
               360, 80, [("1 plate", 350)], vegetarian=True),
        _piece("Khichdi", "کھچڑی", "khichdi", "rice", "sindhi",
               [(rice, 70), ("mung beans raw", 50), (onion, 20), (oil, 10), (salt, 2), (turmeric, 1)],
               340, 60, [("1 bowl", 300)], vegetarian=True),
        _piece("Chana Pulao", "چنا پلاؤ", "chana pulao", "rice", "punjabi",
               [(rice, 150), ("chickpeas raw", 70), (onion, 60), (tomato, 40), (oil, 18), (salt, 2), (cumin, 1)],
               300, 70, [("1 plate", 340)], vegetarian=True),
        _piece("Boiled Basmati Rice", "ابلیے باسمتی چاول", "ubale basmati chawal", "rice", "pakistani",
               [(rice, 100), (salt, 1)], 220, 30, [("1 katori", 150), ("1 plate", 250)], vegetarian=True, vegan=True,
               note="Boiled rice. Water dilutes the raw rice nutrients. No fat is added."),
        _piece("Chicken Karahi", "چکن کڑاہی", "chicken karahi", "chicken", "pashtun",
               spice([(chicken, 500), (tomato, 220), (onion, 80), (oil, 40), ("coriander raw", 10)]),
               40, 140, [("1 serving", 250), ("1 plate", 300)], method="karahi",
               instructions="Cook tomato and chicken in oil until the masala separates. This estimate uses the cooked weight, not the raw weight."),
        _piece("White Chicken Karahi", "وائٹ چکن کڑاہی", "white chicken karahi", "chicken", "punjabi",
               [(chicken, 450), (yogurt, 120), ("cream", 40), (oil, 30), (garlic, 8), (ginger, 8), (salt, 2), ("black pepper", 1)],
               20, 80, [("1 serving", 250)], method="karahi"),
        _piece("Chicken Handi", "چکن ہانڈی", "chicken handi", "chicken", "punjabi",
               spice([(chicken, 400), (onion, 150), (tomato, 100), (yogurt, 80), (oil, 35), ("cream", 20)]),
               60, 100, [("1 serving", 280)], method="handi"),
        _piece("Chicken Makhani", "چکن مکھنی", "chicken makhani", "chicken", "punjabi",
               [(chicken, 350), (tomato, 200), ("butter", 25), ("cream", 50), (oil, 15), (garlic, 8), (ginger, 6), (salt, 2), ("garam masala", 2)],
               40, 90, [("1 serving", 280)], method="simmered"),
        _piece("Butter Chicken", "بٹر چکن", "butter chicken", "chicken", "punjabi",
               [(chicken, 350), (tomato, 180), ("butter", 30), ("cream", 40), (yogurt, 40), (garlic, 6), (ginger, 6), (salt, 2)],
               30, 80, [("1 serving", 280)], method="simmered"),
        _piece("Chicken Tikka", "چکن تکہ", "chicken tikka", "chicken", "punjabi",
               [(chicken, 300), (yogurt, 80), (oil, 15), (garlic, 8), (ginger, 8), (chili, 8), (salt, 2), ("garam masala", 2)],
               0, 70, [("1 piece", 60), ("1 plate", 180)], method="grilled",
               note="Grilling loss concentrates nutrients. Marinade remains partly on the meat. Surface char is not measured."),
        _piece("Chicken Boti", "چکن بوٹی", "chicken boti", "chicken", "punjabi",
               [(chicken, 300), (yogurt, 50), (oil, 20), (garlic, 6), (ginger, 6), (chili, 6), (salt, 2)],
               0, 60, [("1 skewer", 80)], method="grilled"),
        _piece("Chicken Malai Boti", "چکن ملائی بوٹی", "chicken malai boti", "chicken", "karachi",
               [(chicken, 300), ("cream", 40), (yogurt, 40), (oil, 10), (garlic, 5), (ginger, 5), (salt, 2)],
               0, 55, [("1 skewer", 80)], method="grilled"),
        _piece("Chicken Seekh Kebab", "چکن سیخ کباب", "chicken seekh kebab", "chicken", "punjabi",
               [(chicken, 300), (onion, 40), ("chickpea flour", 15), (oil, 12), (garlic, 6), (ginger, 6), (chili, 6), (salt, 2), ("garam masala", 2)],
               0, 50, [("1 seekh", 70)], method="grilled"),
        _piece("Chicken Shami Kebab", "چکن شامی کباب", "chicken shami kebab", "chicken", "punjabi",
               [(chicken, 250), ("chickpeas raw", 40), (onion, 30), (oil, 15), (garlic, 5), (ginger, 5), (salt, 2), ("garam masala", 2)],
               80, 70, [("1 piece", 45)], method="pan fried"),
        _piece("Chicken Korma", "چکن قورمہ", "chicken korma", "chicken", "punjabi",
               [(chicken, 400), (onion, 180), (yogurt, 120), (oil, 40), (garlic, 8), (ginger, 8), (salt, 2), ("garam masala", 2), ("cardamom", 1)],
               40, 120, [("1 serving", 280)], method="korma"),
        _piece("Chicken Qorma", "چکن قورمہ", "chicken qorma", "chicken", "pakistani",
               [(chicken, 400), (onion, 160), (yogurt, 100), (oil, 35), (garlic, 8), (ginger, 8), (salt, 2), ("garam masala", 2)],
               30, 110, [("1 serving", 270)], method="korma"),
        _piece("Chicken Jalfrezi", "چکن جلفریزی", "chicken jalfrezi", "chicken", "pakistani",
               [(chicken, 300), ("bell pepper", 80), (onion, 80), (tomato, 80), (oil, 20), (garlic, 6), (ginger, 6), (chili, 6), (salt, 2)],
               20, 60, [("1 serving", 250)], method="stir fried"),
        _piece("Chicken Achari", "اچاری چکن", "achari chicken", "chicken", "punjabi",
               [(chicken, 350), (onion, 80), (tomato, 80), (yogurt, 50), (oil, 30), ("fennel seed", 2), (chili, 8), (garlic, 6), (salt, 2)],
               20, 70, [("1 serving", 250)], method="braised"),
        _piece("Chicken Kofta", "چکن کوفتہ", "chicken kofta", "chicken", "punjabi",
               [(chicken, 300), (onion, 80), (tomato, 100), (yogurt, 40), (oil, 25), ("chickpea flour", 15), (garlic, 6), (salt, 2)],
               80, 70, [("1 piece", 50)], method="simmered"),
        _piece("Chicken Roast", "چکن روسٹ", "chicken roast", "chicken", "pakistani",
               [(chicken, 400), (yogurt, 40), (oil, 15), (garlic, 8), (ginger, 8), (salt, 2), ("black pepper", 1)],
               0, 90, [("1 piece", 120)], method="roasted"),
        _piece("Chicken Curry", "چکن کری", "chicken curry", "chicken", "pakistani",
               spice([(chicken, 350), (onion, 120), (tomato, 120), (oil, 25)]),
               120, 80, [("1 katori", 200)], method="curry"),
        _piece("Chicken Stew", "چکن اسٹو", "chicken stew", "chicken", "pakistani",
               [(chicken, 300), ("potato raw", 100), ("carrot raw", 60), (onion, 50), (oil, 12), (salt, 2), ("black pepper", 1)],
               200, 60, [("1 bowl", 300)], method="stewed"),
        _piece("Chicken Ginger", "ادرک چکن", "adrak chicken", "chicken", "pakistani",
               [(chicken, 350), (ginger, 30), (onion, 60), (tomato, 40), (oil, 20), (garlic, 6), (salt, 2), (chili, 4)],
               30, 70, [("1 serving", 240)], method="braised"),
        _piece("Chicken Masala", "چکن مسالہ", "chicken masala", "chicken", "pakistani",
               spice([(chicken, 350), (onion, 100), (tomato, 120), (oil, 25), (yogurt, 30)]),
               40, 80, [("1 serving", 250)], method="braised"),
        _piece("Beef Nihari", "بیف نہاری", "beef nihari", "beef_mutton", "karachi",
               [(beef, 400), ("whole wheat flour", 20), (oil, 40), (onion, 80), (ginger, 15), (garlic, 10), (salt, 3), ("garam masala", 3), (chili, 6)],
               350, 150, [("1 bowl", 300)], method="slow simmer",
               note="Long simmering changes weight. The flour slurry is included. Bone broth minerals are not fully represented."),
        _piece("Mutton Nihari", "مٹن نہاری", "mutton nihari", "beef_mutton", "karachi",
               [(lamb, 400), ("whole wheat flour", 20), (oil, 40), (onion, 80), (ginger, 15), (garlic, 10), (salt, 3), ("garam masala", 3)],
               350, 150, [("1 bowl", 300)], method="slow simmer"),
        _piece("Beef Korma", "بیف قورمہ", "beef korma", "beef_mutton", "punjabi",
               [(beef, 400), (onion, 180), (yogurt, 100), (oil, 40), (garlic, 8), (ginger, 8), (salt, 2), ("garam masala", 2)],
               40, 120, [("1 serving", 280)], method="korma"),
        _piece("Mutton Korma", "مٹن قورمہ", "mutton korma", "beef_mutton", "punjabi",
               [(lamb, 400), (onion, 180), (yogurt, 120), (oil, 40), (garlic, 8), (ginger, 8), (salt, 2), ("garam masala", 2)],
               40, 120, [("1 serving", 280)], method="korma"),
        _piece("Mutton Karahi", "مٹن کڑاہی", "mutton karahi", "beef_mutton", "pashtun",
               [(lamb, 450), (tomato, 200), (oil, 45), (ginger, 10), (garlic, 8), (salt, 2), (chili, 8)],
               20, 130, [("1 serving", 250)], method="karahi"),
        _piece("Beef Karahi", "بیف کڑاہی", "beef karahi", "beef_mutton", "pashtun",
               [(beef, 450), (tomato, 200), (oil, 40), (ginger, 10), (garlic, 8), (salt, 2), (chili, 6)],
               20, 120, [("1 serving", 250)], method="karahi"),
        _piece("Mutton Handi", "مٹن ہانڈی", "mutton handi", "beef_mutton", "punjabi",
               [(lamb, 400), (onion, 140), (yogurt, 80), (tomato, 60), (oil, 35), (garlic, 8), (salt, 2)],
               50, 100, [("1 serving", 280)], method="handi"),
        _piece("Beef Qorma", "بیف قورمہ", "beef qorma", "beef_mutton", "pakistani",
               [(beef, 380), (onion, 160), (yogurt, 90), (oil, 35), (garlic, 8), (ginger, 8), (salt, 2)],
               30, 100, [("1 serving", 270)], method="korma"),
        _piece("Beef Seekh Kebab", "بیف سیخ کباب", "beef seekh kebab", "beef_mutton", "punjabi",
               [(beef, 300), (onion, 40), ("chickpea flour", 12), (oil, 12), (garlic, 6), (chili, 6), (salt, 2), ("garam masala", 2)],
               0, 45, [("1 seekh", 70)], method="grilled"),
        _piece("Chapli Kebab", "چپلی کباب", "chapli kebab", "beef_mutton", "pashtun",
               [(beef, 300), (onion, 40), (tomato, 30), ("whole wheat flour", 20), (oil, 25), ("coriander seed", 3), (chili, 8), (salt, 2)],
               0, 40, [("1 piece", 80)], method="pan fried"),
        _piece("Reshmi Kebab", "ریشمی کباب", "reshmi kebab", "chicken", "karachi",
               [(chicken, 300), ("cream", 30), ("cheddar cheese", 20), (oil, 8), (garlic, 4), (salt, 2)],
               0, 40, [("1 piece", 50)], method="grilled"),
        _piece("Gola Kebab", "گولہ کباب", "gola kebab", "beef_mutton", "karachi",
               [(beef, 300), (onion, 30), ("chickpea flour", 15), (oil, 15), (garlic, 5), (chili, 5), (salt, 2)],
               0, 40, [("1 piece", 55)], method="pan fried"),
        _piece("Shami Kebab", "شامی کباب", "shami kebab", "beef_mutton", "punjabi",
               [(beef, 250), ("chickpeas raw", 50), (onion, 30), (oil, 18), (garlic, 5), (ginger, 5), (salt, 2)],
               100, 80, [("1 piece", 40)], method="pan fried"),
        _piece("Haleem", "حلیم", "haleem", "beef_mutton", "pakistani",
               [(beef, 200), ("whole wheat flour", 40), ("lentils raw", 30), ("oats", 20), (onion, 60), (oil, 25), (ginger, 8), (garlic, 8), (salt, 3)],
               500, 180, [("1 bowl", 300)], method="slow simmer",
               note="Haleem is a long-cooked porridge. Oats stand in only when barley is not in the reference set. The result is an estimate."),
        _piece("Paya Curry", "پائے", "paya", "beef_mutton", "punjabi",
               [("tripe beef", 200), (onion, 80), (oil, 30), (ginger, 15), (garlic, 10), (yogurt, 40), (salt, 3), ("garam masala", 2)],
               400, 120, [("1 bowl", 300)], method="slow simmer",
               note="Trotters are represented with a lean tripe reference because a hoof cut is not in the reference set. Collagen is only partly reflected. Estimate only."),
        _piece("Keema Curry", "قیمہ", "keema curry", "beef_mutton", "punjabi",
               spice([(beef, 350), (onion, 120), (tomato, 100), (oil, 30), ("peas raw", 50)]),
               40, 90, [("1 katori", 180)], method="browned"),
        _piece("Aloo Keema", "آلو قیمہ", "aloo keema", "beef_mutton", "punjabi",
               spice([(beef, 280), ("potato raw", 180), (onion, 80), (tomato, 80), (oil, 25)]),
               40, 80, [("1 plate", 250)], method="braised"),
        _piece("Mutton Chops", "مٹن چاپ", "mutton chops", "beef_mutton", "punjabi",
               [(lamb, 350), (yogurt, 40), (oil, 15), (garlic, 6), (ginger, 6), (salt, 2), ("garam masala", 2)],
               0, 70, [("1 piece", 90)], method="grilled"),
        _piece("Raan Roast", "ران روسٹ", "raan roast", "beef_mutton", "pakistani",
               [(lamb, 500), (yogurt, 80), (oil, 20), (garlic, 10), (ginger, 10), (salt, 3), ("red chili powder", 2)],
               0, 120, [("1 slice", 100)], method="roasted"),
        _piece("Beef Stew", "بیف اسٹو", "beef stew", "beef_mutton", "pakistani",
               [(beef, 300), ("potato raw", 100), ("carrot raw", 60), (onion, 50), (oil, 15), (salt, 2)],
               200, 70, [("1 bowl", 320)], method="stewed"),
        _piece("Mutton Stew", "مٹن اسٹو", "mutton stew", "beef_mutton", "pakistani",
               [(lamb, 300), ("potato raw", 100), ("carrot raw", 50), (onion, 50), (oil, 15), (salt, 2)],
               200, 70, [("1 bowl", 320)], method="stewed"),
        _piece("Brain Masala", "مغز", "maghaz masala", "beef_mutton", "punjabi",
               [("beef brain", 200), (onion, 60), (tomato, 50), (oil, 20), (garlic, 5), (ginger, 5), (chili, 4), (salt, 2)],
               20, 50, [("1 serving", 150)], method="sauteed",
               note="Brain composition varies. This is a coarse estimate."),
        _piece("Fried Fish", "فرائی فش", "fried fish", "seafood", "pakistani",
               [("fish raw", 250), ("chickpea flour", 30), (oil, 25), (garlic, 4), (chili, 4), (salt, 2), ("lemon raw", 10)],
               10, 40, [("1 piece", 100)], method="shallow fried"),
        _piece("Lahori Fried Fish", "لاہوری فرائی فش", "lahori fried fish", "seafood", "punjabi",
               [("fish raw", 250), ("chickpea flour", 40), (oil, 35), (garlic, 5), (cumin, 1), (chili, 6), (salt, 2)],
               0, 35, [("1 piece", 110)], method="deep fried",
               note="Only the oil retained in the ingredient list is counted. Oil left in the pan is not."),
        _piece("Grilled Fish", "گرل فش", "grilled fish", "seafood", "balochi",
               [("fish raw", 250), (oil, 8), (garlic, 4), (chili, 3), (salt, 2), ("lemon raw", 15)],
               0, 40, [("1 piece", 150)], method="grilled"),
        _piece("Fish Karahi", "فش کڑاہی", "fish karahi", "seafood", "karachi",
               [("fish raw", 300), (tomato, 160), (oil, 30), (garlic, 6), (ginger, 6), (chili, 6), (salt, 2)],
               20, 70, [("1 serving", 230)], method="karahi"),
        _piece("Fish Tikka", "فش تکہ", "fish tikka", "seafood", "pakistani",
               [("fish raw", 280), (yogurt, 50), (oil, 12), (garlic, 6), (chili, 6), (salt, 2)],
               0, 50, [("1 piece", 80)], method="grilled"),
        _piece("Masala Fish", "مسالہ فش", "masala fish", "seafood", "pakistani",
               [("fish raw", 280), (onion, 70), (tomato, 80), (oil, 20), (garlic, 6), (chili, 5), (salt, 2)],
               30, 50, [("1 serving", 220)], method="braised"),
        _piece("Fish Curry", "فش کری", "fish curry", "seafood", "sindhi",
               [("fish raw", 280), (onion, 70), (tomato, 100), (oil, 18), ("tamarind", 8), (garlic, 6), (chili, 6), (salt, 2)],
               120, 50, [("1 bowl", 250)], method="curry"),
        _piece("Prawn Masala", "جھینگا مسالہ", "prawn masala", "seafood", "karachi",
               [("shrimp raw", 280), (onion, 70), (tomato, 90), (oil, 22), (garlic, 6), (ginger, 6), (chili, 5), (salt, 2)],
               20, 60, [("1 serving", 200)], method="sauteed"),
        _piece("Prawn Karahi", "جھینگا کڑاہی", "prawn karahi", "seafood", "karachi",
               [("shrimp raw", 300), (tomato, 150), (oil, 25), (garlic, 6), (ginger, 6), (chili, 6), (salt, 2)],
               10, 60, [("1 serving", 200)], method="karahi"),
        _piece("Grilled Prawns", "گرل جھینگا", "grilled prawns", "seafood", "balochi",
               [("shrimp raw", 250), (oil, 10), (garlic, 4), ("lemon raw", 10), (salt, 2)],
               0, 40, [("1 piece", 30)], method="grilled"),
        _piece("Fish Biryani", "فش بریانی", "fish biryani", "seafood", "karachi",
               [("fish raw", 220), (rice, 160), (onion, 70), (tomato, 60), (yogurt, 40), (oil, 25), (garlic, 6), (ginger, 6), (salt, 2)],
               280, 60, [("1 plate", 360)], method="dum"),
        _piece("Seafood Curry", "سی فوڈ کری", "seafood curry", "seafood", "karachi",
               [("fish raw", 150), ("shrimp raw", 120), (onion, 60), (tomato, 80), (oil, 18), (garlic, 6), (salt, 2)],
               100, 40, [("1 bowl", 250)], method="curry"),
    ]
    # The list above accidentally may include cuisine_ignored. Strip unknown later.
    recipes.extend(famous)

    vegetables = [
        ("Aloo", "آلو", "aloo", "potato raw"),
        ("Palak", "پالک", "palak", "spinach raw"),
        ("Gobi", "گوبھی", "gobi", "cauliflower raw"),
        ("Bhindi", "بھنڈی", "bhindi", "okra raw"),
        ("Baingan", "بینگن", "baingan", "eggplant raw"),
        ("Gajar", "گاجر", "gajar", "carrot raw"),
        ("Matar", "مٹر", "matar", "peas raw"),
        ("Band gobi", "بند گوبھی", "band gobi", "cabbage raw"),
        ("Kaddu", "کدو", "kaddu", "pumpkin raw"),
        ("Kheera", "کھیرا", "kheera", "cucumber raw"),
        ("Shalgam", "شلجم", "shalgam", "turnip raw"),
        ("Mooli", "مولی", "mooli", "radish raw"),
        ("Karela", "کریلا", "karela", "bitter gourd"),
        ("Lauki", "لوکی", "lauki", "bottle gourd"),
        ("Shimla mirch", "شملہ مرچ", "shimla mirch", "bell pepper"),
        ("Mirch", "مرچ", "mirch", "chili pepper raw"),
        ("Beans", "بینز", "beans", "green beans"),
        ("Mushroom", "مشروم", "mushroom", "mushroom raw"),
        ("Makai", "مکئی", "makai", "corn raw"),
        ("Chukandar", "چکندر", "chukandar", "beet raw"),
        ("Shakarkandi", "شکر قندی", "shakarkandi", "sweet potato raw"),
        ("Methi", "میتھی", "methi", "fenugreek leaves"),
        ("Sarson", "سرسوں", "sarson", "mustard greens"),
        ("Tinda", "ٹینڈا", "tinda", "pumpkin raw"),
        ("Arvi", "اروی", "arvi", "potato raw"),
    ]
    for english, ur, roman, query in vegetables:
        recipes.append(_piece(
            f"{english} sabzi", ur + " سبزی", f"{roman} sabzi", "lentils_vegetarian", "punjabi",
            [(query, 250), (onion, 40), (tomato, 40), (oil, 15), (garlic, 4), (ginger, 3), (chili, 3), (salt, 2), (turmeric, 1), (cumin, 1)],
            30, 70, [("1 katori", 150)], vegetarian=True,
            note="Home-style dry sabzi. Cooked weight is lower than the raw pan weight because water evaporates.",
        ))
        recipes.append(_piece(
            f"{english} salan", ur + " سالن", f"{roman} salan", "lentils_vegetarian", "punjabi",
            [(query, 200), (onion, 60), (tomato, 100), (oil, 18), (yogurt, 30), (garlic, 5), (ginger, 4), (chili, 4), (salt, 2), (turmeric, 1)],
            80, 60, [("1 katori", 180)], vegetarian=True,
        ))

    lentils = [
        ("Daal masoor", "دال مسور", "daal masoor", "lentils raw", "punjabi"),
        ("Daal moong", "دال مونگ", "daal moong", "mung beans raw", "punjabi"),
        ("Daal mash", "دال ماش", "daal mash", "black gram", "punjabi"),
        ("Daal chana", "دال چنا", "daal chana", "chickpeas raw", "punjabi"),
        ("Mixed daal", "مکس دال", "mixed daal", "lentils raw", "pakistani"),
        ("Rajma", "راجما", "rajma", "kidney beans raw", "punjabi"),
        ("Chana masala", "چنا مسالہ", "chana masala", "chickpeas raw", "punjabi"),
        ("Whole masoor", "سبوت مسور", "sabut masoor", "lentils raw", "pakistani"),
    ]
    for name, ur, roman, query, cuisine in lentils:
        recipes.append(_piece(name, ur, roman, "lentils_vegetarian", cuisine,
                              [(query, 80), (onion, 40), (tomato, 40), (oil, 12), (garlic, 5), (ginger, 4), (chili, 3), (salt, 2), (turmeric, 1), (cumin, 1)],
                              320, 80, [("1 katori", 180)], vegetarian=True, method="tadka"))
        recipes.append(_piece(f"Plain boiled {name}", "ابلی " + ur, f"ubali {roman}", "lentils_vegetarian", cuisine,
                              [(query, 80), (salt, 2), (turmeric, 1)],
                              340, 40, [("1 katori", 180)], vegetarian=True, vegan=True, method="boiled"))

    combos = [
        ("Aloo gobi", "آلو گوبھی", "aloo gobi", [("potato raw", 150), ("cauliflower raw", 150)]),
        ("Aloo palak", "آلو پالک", "aloo palak", [("potato raw", 120), ("spinach raw", 180)]),
        ("Palak paneer", "پالک پنیر", "palak paneer", [("spinach raw", 250), ("paneer", 80)]),
        ("Aloo matar", "آلو مٹر", "aloo matar", [("potato raw", 150), ("peas raw", 80)]),
        ("Matar paneer", "مٹر پنیر", "matar paneer", [("peas raw", 120), ("paneer", 80)]),
        ("Baingan bharta", "بینگن کا بھرتا", "baingan bharta", [("eggplant raw", 300)]),
        ("Bhindi masala", "بھنڈی مسالہ", "bhindi masala", [("okra raw", 250)]),
        ("Mix vegetable curry", "مکس سبزی", "mix sabzi", [("potato raw", 60), ("carrot raw", 40), ("peas raw", 40), ("cauliflower raw", 60)]),
        ("Vegetable kofta", "ویجیٹبل کوفتہ", "vegetable kofta", [("potato raw", 100), ("chickpea flour", 40), ("peas raw", 30)]),
        ("Kadhi pakora", "کڑھی پکوڑا", "kadhi pakora", [("yogurt plain", 200), ("chickpea flour", 40)]),
        ("Sarson ka saag", "سرسوں کا ساگ", "sarson ka saag", [("mustard greens", 250), ("spinach raw", 80)]),
        ("Aloo baingan", "آلو بینگن", "aloo baingan", [("potato raw", 120), ("eggplant raw", 150)]),
        ("Palak gosht", "پالک گوشت", "palak gosht", [("spinach raw", 200), (lamb, 150)]),
        ("Aloo gosht", "آلو گوشت", "aloo gosht", [("potato raw", 160), (lamb, 180)]),
        ("Bhindi gosht", "بھنڈی گوشت", "bhindi gosht", [("okra raw", 150), (beef, 160)]),
    ]
    for name, ur, roman, parts in combos:
        veg = all(part[0] not in {lamb, beef, chicken} for part in parts)
        recipes.append(_piece(
            name, ur, roman, "lentils_vegetarian" if veg else "beef_mutton", "punjabi",
            [*parts, (onion, 50), (tomato, 60), (oil, 18), (garlic, 5), (ginger, 4), (salt, 2), (turmeric, 1), (cumin, 1)],
            40, 70, [("1 katori", 180)], vegetarian=veg,
        ))

    breads = [
        ("Chapati", "چپاتی", "chapati", [("whole wheat flour", 40), (salt, 0.4)], 18, 8, [("1 roti", 42)]),
        ("Roti", "روٹی", "roti", [("whole wheat flour", 40), (salt, 0.4)], 18, 8, [("1 roti", 42)]),
        ("Tandoori roti", "تندوری روٹی", "tandoori roti", [("whole wheat flour", 55)], 22, 12, [("1 roti", 55)]),
        ("Whole wheat roti", "گندم کی روٹی", "gehun ki roti", [("whole wheat flour", 45)], 20, 8, [("1 roti", 48)]),
        ("Naan", "نان", "naan", [("wheat flour", 70), (yogurt, 15), (oil, 6)], 15, 12, [("1 naan", 90)]),
        ("Roghni naan", "روغنی نان", "roghni naan", [("wheat flour", 70), (yogurt, 15), (oil, 12)], 12, 10, [("1 naan", 95)]),
        ("Garlic naan", "گارلک نان", "garlic naan", [("wheat flour", 70), (yogurt, 12), (oil, 8), (garlic, 6)], 12, 10, [("1 naan", 95)]),
        ("Butter naan", "بٹر نان", "butter naan", [("wheat flour", 70), (yogurt, 12), ("butter", 8)], 12, 10, [("1 naan", 95)]),
        ("Kulcha", "کلچہ", "kulcha", [("wheat flour", 65), (yogurt, 15), (oil, 8)], 10, 10, [("1 kulcha", 80)]),
        ("Sheermal", "شیرمال", "sheermal", [("wheat flour", 60), ("milk whole", 25), ("sugar", 8), (oil, 8)], 5, 12, [("1 piece", 70)]),
        ("Taftan", "تافتان", "taftan", [("wheat flour", 70), ("milk whole", 20), (oil, 10), ("sugar", 6)], 8, 12, [("1 piece", 80)]),
        ("Missi roti", "مسی روٹی", "missi roti", [("chickpea flour", 30), ("whole wheat flour", 20), (oil, 6), (chili, 3), (salt, 1)], 16, 8, [("1 roti", 50)]),
        ("Makki ki roti", "مکی کی روٹی", "makki ki roti", [("corn flour", 50), (salt, 1)], 25, 10, [("1 roti", 55)]),
        ("Paratha", "پراٹھا", "paratha", [("whole wheat flour", 50), (oil, 12), (salt, 1)], 18, 8, [("1 paratha", 70)]),
        ("Lachha paratha", "لچھا پراٹھا", "lachha paratha", [("whole wheat flour", 55), (oil, 16), (salt, 1)], 16, 8, [("1 paratha", 75)]),
        ("Puri", "پوری", "puri", [("wheat flour", 30), (oil, 10), (salt, 0.5)], 12, 6, [("1 puri", 30)]),
        ("Poori", "پوری", "poori", [("whole wheat flour", 30), (oil, 10), (salt, 0.5)], 12, 6, [("1 poori", 30)]),
        ("Sajji bread", "سجی کی روٹی", "sajji roti", [("whole wheat flour", 70), (salt, 1)], 25, 15, [("1 piece", 70)], "balochi"),
        ("Plain paratha", "سادہ پراٹھا", "sada paratha", [("whole wheat flour", 50), (oil, 10), (salt, 1)], 18, 8, [("1 paratha", 65)]),
        ("Aloo paratha", "آلو پراٹھا", "aloo paratha", [("whole wheat flour", 50), ("potato raw", 60), (oil, 12), (chili, 3), (salt, 1)], 10, 15, [("1 paratha", 110)]),
        ("Anda paratha", "انڈا پراٹھا", "anda paratha", [("whole wheat flour", 45), ("egg whole raw", 50), (oil, 12), (salt, 1)], 12, 12, [("1 paratha", 100)]),
        ("Keema paratha", "قیمہ پراٹھا", "keema paratha", [("whole wheat flour", 50), (beef, 40), (oil, 12), (salt, 1)], 12, 14, [("1 paratha", 110)]),
        ("Chicken paratha", "چکن پراٹھا", "chicken paratha", [("whole wheat flour", 50), (chicken, 40), (oil, 12), (salt, 1)], 12, 14, [("1 paratha", 110)]),
    ]
    for name, ur, roman, ingredients, water, loss, servings, *rest in [(b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7] if len(b) > 7 else "pakistani") for b in breads]:
        cuisine = rest[0] if isinstance(rest, tuple) else rest
        # rest handling is messy because of the comprehension. Handle below.
    for item in breads:
        cuisine = item[7] if len(item) > 7 else "pakistani"
        name, ur, roman, ingredients, water, loss, servings = item[:7]
        meat = any(part[0] in {beef, chicken, lamb} for part in ingredients)
        egg = any(part[0] == "egg whole raw" for part in ingredients)
        dairy = any(part[0] in {yogurt, "milk whole", "butter"} for part in ingredients)
        category = "breakfast" if "paratha" in name.lower() else "breads"
        recipes.append(_piece(name, ur, roman, category, cuisine, ingredients, water, loss, servings,
                              vegetarian=not meat, vegan=not meat and not egg and not dairy,
                              note="Bread nutrition uses the cooked weight after water loss. A single piece serving is the recipe yield."))

    breakfasts = [
        _piece("Halwa puri", "حلوا پوری", "halwa puri", "breakfast", "punjabi",
               [("semolina", 40), ("sugar", 20), (oil, 15), ("wheat flour", 40), (oil, 12)],
               40, 20, [("1 plate", 180)]),
        _piece("Chana for halwa puri", "چنے", "chane", "breakfast", "punjabi",
               [("chickpeas raw", 80), (onion, 30), (tomato, 20), (oil, 10), (salt, 2), (cumin, 1)],
               200, 40, [("1 katori", 150)], vegetarian=True),
        _piece("Omelette", "آملیٹ", "omelette", "breakfast", "pakistani",
               [("egg whole raw", 100), (onion, 20), (chili, 5), (oil, 8), (salt, 1)],
               0, 15, [("1 omelette", 110)]),
        _piece("Fried egg", "تلا انڈا", "tala anda", "breakfast", "pakistani",
               [("egg whole raw", 50), (oil, 5), (salt, 0.5)], 0, 6, [("1 egg", 48)]),
        _piece("Boiled egg", "ابلا انڈا", "ubla anda", "breakfast", "pakistani",
               [("egg whole raw", 50), (salt, 0.3)], 0, 4, [("1 egg", 46)],
               note="Boiling does not add fat. A little water loss is applied."),
        _piece("Scrambled egg", "اسکرمبل انڈا", "scrambled anda", "breakfast", "pakistani",
               [("egg whole raw", 100), ("milk whole", 15), (oil, 6), (salt, 1)], 0, 12, [("1 serving", 100)]),
        _piece("Bread and butter", "ڈبل روٹی اور مکھن", "double roti butter", "breakfast", "pakistani",
               [("bread white", 60), ("butter", 10)], 0, 0, [("2 slices", 70)], vegetarian=True),
        _piece("Toast", "ٹوسٹ", "toast", "breakfast", "pakistani",
               [("bread white", 30)], 0, 3, [("1 slice", 27)], vegetarian=True, vegan=True),
        _piece("Bun kebab", "بن کباب", "bun kebab", "street_food", "karachi",
               [("bread white", 70), (beef, 70), (onion, 20), ("chickpea flour", 10), (oil, 12), (salt, 1)],
               0, 15, [("1 bun", 160)]),
        _piece("Shami bun", "شامی بن", "shami bun", "street_food", "karachi",
               [("bread white", 70), (beef, 50), ("chickpeas raw", 15), (onion, 15), (oil, 10), (salt, 1)],
               20, 15, [("1 bun", 150)]),
        _piece("Aloo bhujia", "آلو بھجیا", "aloo bhujia", "breakfast", "punjabi",
               [("potato raw", 200), (onion, 40), (tomato, 30), (oil, 15), (chili, 4), (salt, 2), (cumin, 1)],
               10, 40, [("1 plate", 180)], vegetarian=True),
        _piece("Breakfast sandwich", "ناشتہ سینڈوچ", "nashta sandwich", "breakfast", "pakistani",
               [("bread white", 60), ("egg whole raw", 50), (oil, 6), (onion, 10)], 0, 8, [("1 sandwich", 110)]),
    ]
    recipes.extend(breakfasts)

    streets = [
        ("Aloo samosa", "آلو سموسہ", "aloo samosa", [("potato raw", 80), ("wheat flour", 30), ("peas raw", 20), (oil, 18), (cumin, 1), (salt, 1)]),
        ("Keema samosa", "قیمہ سموسہ", "keema samosa", [(beef, 60), ("wheat flour", 30), (onion, 15), (oil, 18), (salt, 1)]),
        ("Chicken samosa", "چکن سموسہ", "chicken samosa", [(chicken, 60), ("wheat flour", 30), (onion, 15), (oil, 16), (salt, 1)]),
        ("Vegetable pakora", "سبزی پکوڑا", "sabzi pakora", [("chickpea flour", 40), ("spinach raw", 30), (onion, 20), (oil, 18), (salt, 1)]),
        ("Onion pakora", "پیاز پکوڑا", "piaz pakora", [("chickpea flour", 40), (onion, 50), (oil, 20), (chili, 4), (salt, 1)]),
        ("Chicken roll", "چکن رول", "chicken roll", [("wheat flour", 50), (chicken, 70), (onion, 20), (oil, 10), (yogurt, 15)]),
        ("Paratha roll", "پراٹھا رول", "paratha roll", [("whole wheat flour", 50), (chicken, 60), ("egg whole raw", 40), (oil, 12), (onion, 15)]),
        ("Zinger burger", "زنگر برگر", "zinger burger", [(chicken, 110), ("bread white", 70), (oil, 18), ("mayonnaise", 15)]),
        ("Shami burger", "شامی برگر", "shami burger", [("bread white", 70), (beef, 60), ("chickpeas raw", 15), (oil, 10), (onion, 15)]),
        ("Dahi bhalla", "دہی بھلے", "dahi bhalla", [("yogurt plain", 120), ("black gram", 40), (cumin, 1), (salt, 1)]),
        ("Chana chaat", "چنا چاٹ", "chana chaat", [("chickpeas raw", 80), (onion, 30), (tomato, 30), (yogurt, 30), ("tamarind", 5), (salt, 1)]),
        ("Fruit chaat", "فروٹ چاٹ", "fruit chaat", [("banana raw", 40), ("apple raw", 40), ("guava raw", 40), ("pomegranate raw", 20), ("lemon raw", 5)]),
        ("Papri chaat", "پاپڑی چاٹ", "papri chaat", [("wheat flour", 30), (oil, 10), ("chickpeas raw", 30), (yogurt, 40), ("potato raw", 30)]),
        ("Gol gappay", "گول گپے", "gol gappay", [("wheat flour", 20), ("chickpeas raw", 30), ("potato raw", 30), ("tamarind", 8), (cumin, 1)]),
        ("Pani puri", "پانی پوری", "pani puri", [("wheat flour", 20), ("chickpeas raw", 25), ("potato raw", 25), ("tamarind", 8)]),
        ("Aloo tikki", "آلو ٹکی", "aloo tikki", [("potato raw", 120), ("chickpea flour", 15), (oil, 15), (chili, 3), (salt, 1)]),
        ("Fries", "فرائز", "fries", [("potato raw", 150), (oil, 15), (salt, 1)]),
        ("Chicken shawarma", "چکن شوارما", "chicken shawarma", [("wheat flour", 60), (chicken, 80), (yogurt, 20), (oil, 10), (garlic, 4)]),
        ("Chicken cheese roll", "چکن چیز رول", "chicken cheese roll", [("wheat flour", 50), (chicken, 60), ("cheddar cheese", 20), (oil, 10)]),
        ("Seekh kebab roll", "سیخ کباب رول", "seekh roll", [("wheat flour", 50), (beef, 70), (onion, 20), (oil, 10)]),
        ("Anda burger", "انڈا برگر", "anda burger", [("bread white", 70), ("egg whole raw", 50), (oil, 8), (onion, 10)]),
        ("Kachori", "کچوری", "kachori", [("wheat flour", 35), ("lentils raw", 25), (oil, 14), (cumin, 1), (salt, 1)]),
        ("Daal kachori", "دال کچوری", "daal kachori", [("wheat flour", 35), ("lentils raw", 30), (oil, 14), (salt, 1)]),
        ("Chicken patties", "چکن پیٹیز", "chicken patties", [("wheat flour", 40), (chicken, 50), ("potato raw", 30), (oil, 12)]),
        ("Club sandwich", "کلب سینڈوچ", "club sandwich", [("bread white", 70), (chicken, 40), ("egg whole raw", 30), ("mayonnaise", 10)]),
        ("Vegetable pizza slice", "ویجیٹبل پیزا", "vegetable pizza", [("wheat flour", 50), ("cheddar cheese", 25), (tomato, 30), ("bell pepper", 20), (oil, 6)]),
    ]
    for name, ur, roman, ingredients in streets:
        meat = any(q in {beef, chicken, lamb, "shrimp raw", "fish raw"} for q, _ in ingredients)
        recipes.append(_piece(name, ur, roman, "street_food", "karachi", ingredients, 0, 15, [("1 piece", 80)],
                              vegetarian=not meat,
                              note="Street-food estimate. Frying oil left in the kadhai is not counted; only the oil listed is."))

    desserts = [
        ("Gulab jamun", "گلاب جامن", "gulab jamun", [("milk powder", 40), ("wheat flour", 8), (oil, 10), ("sugar", 30)], 25, 10),
        ("Ras malai", "رس ملائی", "ras malai", [("milk whole", 200), ("sugar", 25), ("milk powder", 20)], 0, 40),
        ("Kheer", "کھیر", "kheer", [(rice, 30), ("milk whole", 250), ("sugar", 25)], 0, 50),
        ("Rice kheer", "چاول کی کھیر", "chawal ki kheer", [(rice, 35), ("milk whole", 260), ("sugar", 25), ("cardamom", 0.3)], 0, 50),
        ("Gajar halwa", "گاجر کا حلوا", "gajar ka halwa", [("carrot raw", 200), ("milk whole", 120), ("sugar", 30), ("ghee", 15)], 0, 140),
        ("Suji halwa", "سوجی کا حلوا", "suji halwa", [("semolina", 50), ("sugar", 30), ("ghee", 15)], 80, 20),
        ("Habshi halwa", "حبشی حلوا", "habshi halwa", [("wheat flour", 30), ("milk whole", 80), ("sugar", 25), ("ghee", 15)], 20, 30),
        ("Jalebi", "جلیبی", "jalebi", [("wheat flour", 30), (yogurt, 15), (oil, 15), ("sugar", 30)], 20, 10),
        ("Barfi", "برفی", "barfi", [("milk powder", 40), ("sugar", 25), ("ghee", 8)], 10, 8),
        ("Besan laddu", "بیسن کے لڈو", "besan laddu", [("chickpea flour", 40), ("ghee", 15), ("sugar", 25)], 0, 8),
        ("Kulfi", "کلفی", "kulfi", [("milk whole", 150), ("sugar", 20), ("almonds", 5)], 0, 40),
        ("Falooda", "فالودہ", "falooda", [("milk whole", 150), ("vermicelli", 20), ("sugar", 20), ("ice cream vanilla", 30)], 20, 10),
        ("Rabri", "ربڑی", "rabri", [("milk whole", 250), ("sugar", 25)], 0, 120),
        ("Zarda", "زردہ", "zarda", [(rice, 80), ("sugar", 30), (oil, 10), ("raisins", 8)], 140, 30),
        ("Sheer khurma", "شیر خرما", "sheer khurma", [("vermicelli", 30), ("milk whole", 200), ("sugar", 25), ("dates", 15), ("almonds", 5)], 0, 30),
        ("Shahi tukray", "شاہی ٹکڑے", "shahi tukray", [("bread white", 40), ("milk whole", 120), ("sugar", 20), (oil, 10)], 0, 25),
        ("Firni", "فرنی", "firni", [("rice", 25), ("milk whole", 220), ("sugar", 22)], 0, 40),
        ("Sohan halwa", "سوہن حلوا", "sohan halwa", [("corn flour", 30), ("ghee", 15), ("sugar", 30), ("milk whole", 40)], 10, 20),
        ("Petha", "پیتھا", "petha", [("pumpkin raw", 100), ("sugar", 40)], 30, 40),
        ("Sooji biscuit", "سوجی بسکٹ", "suji biscuit", [("semolina", 30), ("wheat flour", 15), ("sugar", 12), ("butter", 10)], 5, 8),
    ]
    for name, ur, roman, ingredients, water, loss in desserts:
        recipes.append(_piece(name, ur, roman, "desserts", "pakistani", ingredients, water, loss, [("1 piece", 40)],
                              vegetarian=True, note="Dessert estimate from household ingredient weights. Syrup left in the bowl is not all absorbed."))

    drinks = [
        ("Doodh patti", "دودھ پتی", "doodh patti", [("milk whole", 180), ("sugar", 12), ("tea brewed", 30)], 0, 15, [("1 cup", 180)]),
        ("Karak chai", "کڑک چائے", "karak chai", [("milk whole", 100), ("water", 80), ("sugar", 14), ("tea brewed", 20)], 0, 25, [("1 cup", 160)]),
        ("Milk tea with sugar", "دودھ والی چائے", "doodh wali chai", [("milk whole", 120), ("water", 60), ("sugar", 10)], 0, 15, [("1 cup", 160)]),
        ("Tea without sugar", "بغیر شکر چائے", "baghair shakar chai", [("milk whole", 80), ("water", 100)], 0, 15, [("1 cup", 160)]),
        ("Black tea", "کالی چائے", "kali chai", [("water", 200), ("tea brewed", 20)], 0, 10, [("1 cup", 200)]),
        ("Green tea", "سبز چائے", "sabz chai", [("water", 220)], 0, 10, [("1 cup", 200)]),
        ("Black coffee", "کالی کافی", "kali coffee", [("coffee brewed", 200)], 0, 0, [("1 cup", 200)]),
        ("Sweet lassi", "میٹھی لسی", "meethi lassi", [(yogurt, 160), ("water", 80), ("sugar", 15)], 0, 0, [("1 glass", 250)]),
        ("Salted lassi", "نمکی لسی", "namkeen lassi", [(yogurt, 160), ("water", 90), (salt, 1)], 0, 0, [("1 glass", 250)]),
        ("Mango lassi", "آم کی لسی", "aam lassi", [(yogurt, 120), ("mango raw", 80), ("sugar", 10)], 0, 0, [("1 glass", 200)]),
        ("Fresh mango juice", "آم کا جوس", "aam ka juice", [("mango raw", 150), ("water", 50)], 0, 0, [("1 glass", 200)]),
        ("Orange juice", "مالٹے کا جوس", "malta juice", [("orange juice", 200)], 0, 0, [("1 glass", 200)]),
        ("Sugarcane juice", "گنے کا جوس", "ganne ka juice", [("sugar", 25), ("water", 200), ("lemon raw", 5)], 0, 0, [("1 glass", 220)]),
        ("Rooh Afza drink", "روح افزا", "rooh afza", [("sugar", 20), ("water", 220)], 0, 0, [("1 glass", 240)]),
        ("Lemon soda", "لیمو سوڈا", "lemon soda", [("lemon raw", 20), ("sugar", 12), ("water", 220)], 0, 0, [("1 glass", 250)]),
        ("Cola", "کولڈ ڈرنک", "cold drink", [("cola", 250)], 0, 0, [("1 glass", 250)]),
        ("Milk", "دودھ", "doodh", [("milk whole", 200)], 0, 0, [("1 glass", 200)]),
        ("Banana shake", "کیلا شیک", "kela shake", [("banana raw", 80), ("milk whole", 180), ("sugar", 8)], 0, 0, [("1 glass", 250)]),
        ("Mango shake", "آم شیک", "aam shake", [("mango raw", 80), ("milk whole", 180), ("sugar", 8)], 0, 0, [("1 glass", 250)]),
        ("Dates shake", "کھجور شیک", "khajoor shake", [("dates", 30), ("milk whole", 200)], 0, 0, [("1 glass", 230)]),
        ("Cold coffee", "کولڈ کافی", "cold coffee", [("coffee brewed", 80), ("milk whole", 150), ("sugar", 12)], 0, 0, [("1 glass", 230)]),
        ("Almond milk", "بادام کا دودھ", "badaam doodh", [("almonds", 15), ("water", 200)], 0, 0, [("1 glass", 200)]),
    ]
    drink_notes = {
        "Sugarcane juice": "Pressed cane was not in the reference set, so this is sugar in water and lemon. Treat the calories as a rough estimate.",
        "Rooh Afza drink": "The branded syrup has no verified label in this catalogue, so the record is only sweetened water and may understate a real glass.",
        "Almond milk": "Homemade almond drink. A kitchen may strain out pulp; this estimate keeps the almond nutrients.",
        "Green tea": "Unsweetened green tea is represented as hot water because dry leaves at a normal brew contribute almost no energy.",
    }
    for item in drinks:
        name, ur, roman, ingredients, water, loss, servings = item[:7]
        extra = {"note": drink_notes[name]} if name in drink_notes else {}
        recipes.append(_piece(name, ur, roman, "beverages", "pakistani", ingredients, water, loss, servings, **extra))

    condiments = [
        ("Cucumber raita", "کھیرا رائتہ", "kheera raita", [(yogurt, 100), ("cucumber raw", 40), (salt, 1), (cumin, 0.5)], "condiments"),
        ("Mint raita", "پودینہ رائتہ", "podina raita", [(yogurt, 100), ("mint raw", 8), (salt, 1)], "condiments"),
        ("Imli chutney", "املی چٹنی", "imli chutney", [("tamarind", 30), ("sugar", 20), (chili, 3), (salt, 1), ("water", 40)], "condiments"),
        ("Dhaniya chutney", "دھنیا چٹنی", "dhaniya chutney", [("coriander raw", 40), (chili, 8), ("lemon raw", 10), (salt, 1)], "condiments"),
        ("Mixed pickle achar", "اچار", "achar", [("lemon raw", 40), ("carrot raw", 20), (oil, 15), (salt, 4), ("red chili powder", 2), ("fennel seed", 1)], "condiments"),
        ("Green salad", "سبز سلاد", "sabz salad", [("cucumber raw", 40), (tomato, 40), (onion, 20), ("lemon raw", 5)], "snacks"),
        ("Kachumber", "کچومر", "kachumber", [(onion, 30), (tomato, 40), ("cucumber raw", 30), (chili, 3), ("lemon raw", 5)], "snacks"),
    ]
    for name, ur, roman, ingredients, category in condiments:
        recipes.append(_piece(name, ur, roman, category, "pakistani", ingredients, 0, 0, [("1 tablespoon", 15)],
                              vegetarian=True, note="Condiment estimate. Achar salt is high because salt is an ingredient, not a guess."))

    regional = [
        _piece("Sajji", "سجی", "sajji", "beef_mutton", "balochi",
               [(lamb, 400), (salt, 3), ("black pepper", 1), (oil, 8)], 0, 80, [("1 plate", 250)], method="roasted",
               note="Whole-animal sajji is more than this boneless portion. The figure is a spice-roasted meat estimate."),
        _piece("Dampukht mutton", "دم پخت", "dampukht", "beef_mutton", "sindhi",
               [(lamb, 350), (onion, 100), (yogurt, 80), (oil, 30), (garlic, 8), (ginger, 8), (salt, 2)], 40, 90, [("1 serving", 280)], method="dum"),
        _piece("Namkeen gosht", "نمکین گوشت", "namkeen gosht", "beef_mutton", "punjabi",
               [(lamb, 350), (salt, 3), ("black pepper", 1), (oil, 10), (ginger, 6)], 20, 80, [("1 serving", 220)]),
        _piece("Bihari kebab", "بہاری کباب", "bihari kebab", "beef_mutton", "karachi",
               [(beef, 300), (yogurt, 40), (oil, 15), ("red chili powder", 3), ("garam masala", 2), (garlic, 6), (salt, 2)],
               0, 50, [("1 skewer", 80)], method="grilled"),
        _piece("Katakat", "کٹا کٹ", "katakat", "beef_mutton", "karachi",
               [(beef, 120), ("beef liver", 40), ("beef brain", 30), (onion, 40), (tomato, 30), (oil, 20), (ginger, 5), (garlic, 5), (salt, 2)],
               0, 40, [("1 plate", 180)],
               note="Organ-meat mix. Pieces vary widely by stall. This is only an estimate."),
        _piece("Kashmiri rogan josh", "روغن جوش", "rogan josh", "beef_mutton", "kashmiri",
               [(lamb, 350), (yogurt, 100), (oil, 35), (onion, 80), (garlic, 8), (ginger, 8), ("fennel seed", 2), (salt, 2)],
               40, 90, [("1 serving", 260)]),
        _piece("Kashmiri chai", "کشمیری چائے", "kashmiri chai", "beverages", "kashmiri",
               [("water", 200), ("salt", 0.5), ("almonds", 5)], 0, 20, [("1 cup", 160)],
               note="Pink noon chai needs a specific tea and soda. Those were not assigned invented values. This is a salted almond tea estimate."),
        _piece("Gilgit apricot stew", "خوبانی", "khubani", "snacks", "gilgit_baltistan",
               [("raisins", 20), ("water", 150), ("sugar", 5)], 0, 10, [("1 bowl", 150)],
               note="Dried apricot was not matched, so raisins stand in and the record stays an estimate."),
        _piece("Multani sohan halwa", "ملتان سوہن حلوا", "multani sohan halwa", "desserts", "multani",
               [("corn flour", 40), ("ghee", 20), ("sugar", 35), ("milk whole", 30), ("almonds", 5)], 10, 20, [("1 piece", 40)]),
        _piece("South Punjab mutton chowk", "جنوبی پنجاب مٹن", "south punjab mutton", "beef_mutton", "south_punjab",
               [(lamb, 320), (onion, 100), (tomato, 40), (oil, 30), (yogurt, 40), (garlic, 6), (salt, 2)], 30, 80, [("1 serving", 250)]),
        _piece("Peshawari chapli plate", "پشوری چپلی", "peshawari chapli", "beef_mutton", "kpk",
               [(beef, 280), (tomato, 40), (onion, 30), ("whole wheat flour", 15), (oil, 22), ("coriander seed", 2), (salt, 2)],
               0, 35, [("1 piece", 90)]),
        _piece("Balochi kaak", "کاک", "kaak", "breads", "balochi",
               [("whole wheat flour", 80), (salt, 1), (oil, 6)], 25, 18, [("1 piece", 80)], vegan=True),
        _piece("Sindhi kadhi", "سندھی کڑھی", "sindhi kadhi", "lentils_vegetarian", "sindhi",
               [("chickpea flour", 30), (yogurt, 80), ("okra raw", 40), ("tamarind", 6), (oil, 12), (salt, 2)],
               250, 40, [("1 bowl", 250)], vegetarian=True),
        _piece("Karachi bun kebab double", "ڈبل بن کباب", "double bun kebab", "street_food", "karachi",
               [("bread white", 80), (beef, 100), (onion, 25), (oil, 15), ("chickpea flour", 10), (salt, 1)],
               0, 20, [("1 bun", 200)]),
    ]
    recipes.extend(regional)

    # Restaurant-style retained fat variants of common home dishes.
    for base_slug, title in [
        ("chicken-karahi", "Restaurant-style chicken karahi"),
        ("chicken-biryani", "Restaurant-style chicken biryani"),
        ("beef-nihari", "Restaurant-style beef nihari"),
        ("haleem", "Restaurant-style haleem"),
        ("chicken-korma", "Restaurant-style chicken korma"),
        ("mutton-karahi", "Restaurant-style mutton karahi"),
    ]:
        source = next((item for item in recipes if item["slug"] == base_slug or slugify(item["name_en"]) == base_slug), None)
        if not source:
            continue
        variant = deepcopy(source)
        variant["name_en"] = title
        variant["slug"] = slugify(title)
        variant["name_roman"] = title.lower()
        variant["ingredients"] = [
            (query, grams * 1.6 if "oil" in query or query == "ghee" or query == "butter" else grams)
            for query, grams in variant["ingredients"]
        ]
        variant["note"] = "Restaurant-style estimate with more retained cooking fat than the home version. It is not a measured plate from a named restaurant."
        variant["confidence"] = "low"
        recipes.append(variant)

    cleaned = []
    for recipe in recipes:
        recipe.pop("cuisine_ignored", None)
        recipe["slug"] = slugify(recipe.get("slug") or recipe["name_en"])
        recipe["ingredients"] = [(query, grams) for query, grams in recipe["ingredients"] if grams > 0]
        cleaned.append(recipe)
    return cleaned
