from seeds.catalog import build_catalog


def test_catalogue_is_large_and_recipes_are_calculated():
    catalog = build_catalog()
    stats = catalog["stats"]
    assert stats["total"] >= 1000
    assert stats["recipe_estimate"] >= 200
    assert stats["imported_usda"] >= 1000
    karahi = next(food for food in catalog["foods"] if food["slug"] == "chicken-karahi")
    assert karahi["data_origin"] == "recipe_estimate"
    assert karahi["cooked_weight_g"] != karahi["raw_weight_g"]
    assert karahi["per_100g"]["energy_kcal"] is not None
    slugs = [food["slug"] for food in catalog["foods"]]
    assert len(slugs) == len(set(slugs))
