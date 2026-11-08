# Food database guide

The catalogue is built by `backend/seeds/catalog.py` and written by `backend/seeds/seed.py`.

Three origins are stored on every food:

- `imported_usda` — USDA FoodData Central SR Legacy, public domain. The original FDC id is kept on the source row. Slugs look like `usda-171077`.
- `compiled_reference` — a small set of staple values used when a recipe ingredient did not match a USDA description cleanly. These are marked medium confidence.
- `recipe_estimate` — a Pakistani dish whose nutrients were calculated from ingredient grams, added water and water loss. These are estimates, not laboratory assays.

Search matches English, Urdu, Roman Urdu and the combined `search_text`. If fewer than three SQL matches come back, a fuzzy token match (threshold 72) fills the page. Recipe estimates are ordered ahead of generic ingredients so "biryani" prefers the dish.

## Adding foods without changing code

- Admin screen: add one food, verify a row, or upload CSV/JSON.
- CSV columns: `name_en`, `name_ur`, `name_roman`, `energy_kcal`, `protein_g`, `carbohydrate_g`, `fat_g`, `saturated_fat_g`, `fibre_g`, `sugar_g`, `sodium_mg`. Leave a cell blank when the nutrient is unknown. A row with no energy value is skipped rather than stored as zero.
- JSON: a list of objects with the same fields.
- USDA API: `backend/scripts/fetch_usda_reference.py` can pull from FoodData Central when `USDA_API_KEY` is set. The bundled file was converted from the SR Legacy JSON by `backend/scripts/convert_sr_legacy.py`.
- Pakistan Food Composition Table / FAO INFOODS: https://www.fao.org/infoods/infoods/tables-and-databases/pakistan/en/ — the file is not included. When you have a usable extract, import it through the CSV/JSON path and record the source name.

Re-run `python -m seeds.seed` after editing the generator. Duplicate slugs are not inserted twice.

Current counts are in `FOOD_DATABASE_COVERAGE.md`. Verified stays at zero until an administrator marks a row in the admin UI. Regional dishes are concentrated in Punjabi, Karachi and general Pakistani labels. Gilgit-Baltistan, Multan and Khyber Pakhtunkhwa have only a few named specialties in this seed and should be expanded from sourced recipes, not invented calories.
