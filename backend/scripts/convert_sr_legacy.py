"""Trim the USDA SR Legacy JSON archive into the FitDesi reference cache.

Download FoodData_Central_sr_legacy_food_json_2018-04.zip from
https://fdc.nal.usda.gov/download-datasets and pass its path as the argument.
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "seeds" / "data" / "usda_reference.json"
SKIP = ("baby food", "infant formula", "infant", "alcoholic", " beer", "wine,", "whiskey", "whisky", "vodka", "liqueur")
WANTED = {
    1008: "energy_kcal",
    1003: "protein_g",
    1005: "carbohydrate_g",
    1004: "fat_g",
    1258: "saturated_fat_g",
    1079: "fibre_g",
    2000: "sugar_g",
    1063: "sugar_g",
    1093: "sodium_mg",
}


def nutrients(food: dict) -> dict:
    values = {}
    for item in food.get("foodNutrients") or []:
        nutrient = item.get("nutrient") or {}
        nutrient_id = nutrient.get("id")
        field = WANTED.get(nutrient_id)
        if field is None:
            name = (nutrient.get("name") or "").lower()
            unit = (nutrient.get("unitName") or "").lower()
            if name == "energy" and unit == "kcal":
                field = "energy_kcal"
            else:
                continue
        if field not in values and item.get("amount") is not None:
            values[field] = item.get("amount")
    return values


def main() -> None:
    archive = Path(sys.argv[1])
    with zipfile.ZipFile(archive) as bundle:
        name = bundle.namelist()[0]
        payload = json.loads(bundle.read(name))
    foods = payload.get("SRLegacyFoods") or payload
    kept = []
    for food in foods:
        description = food.get("description") or ""
        low = description.lower()
        if any(word in low for word in SKIP):
            continue
        parsed = nutrients(food)
        if parsed.get("energy_kcal") is None:
            continue
        kept.append({
            "fdc_id": food.get("fdcId"),
            "description": description,
            "data_type": "SR Legacy",
            "food_category": (food.get("foodCategory") or {}).get("description") if isinstance(food.get("foodCategory"), dict) else food.get("foodCategory"),
            "energy_kcal": parsed.get("energy_kcal"),
            "protein_g": parsed.get("protein_g"),
            "carbohydrate_g": parsed.get("carbohydrate_g"),
            "fat_g": parsed.get("fat_g"),
            "saturated_fat_g": parsed.get("saturated_fat_g"),
            "fibre_g": parsed.get("fibre_g"),
            "sugar_g": parsed.get("sugar_g"),
            "sodium_mg": parsed.get("sodium_mg"),
        })
    OUT.write_text(json.dumps({
        "source": "USDA FoodData Central SR Legacy",
        "source_url": "https://fdc.nal.usda.gov/",
        "dataset": "FoodData_Central_sr_legacy_food_json_2018-04",
        "licence_note": "USDA FoodData Central data is US government work and is in the public domain. fdc_id values are preserved.",
        "count": len(kept),
        "foods": kept,
    }), encoding="utf-8")
    print(f"kept {len(kept)} -> {OUT}")


if __name__ == "__main__":
    main()
