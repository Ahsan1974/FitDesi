# FitDesi food database coverage

These counts come from the seed catalogue. Verified means an administrator reviewed the row.
Imported USDA values are copied from FoodData Central SR Legacy and keep their FDC ids.
Recipe rows are calculated from ingredient weights and a cooked yield. They are estimates.
Compiled references are rounded published-style values used when a USDA row did not match a recipe ingredient.

- Total foods: 8013
- Verified foods: 0
- Awaiting verification: 8013
- USDA imports: 7617
- Compiled references: 113
- Recipe estimates: 283
- Ingredient records: 7730

## Foods by cuisine label

- balochi: 5
- general: 7730
- gilgit_baltistan: 1
- karachi: 47
- kashmiri: 2
- kpk: 1
- multani: 1
- pakistani: 99
- pashtun: 7
- punjabi: 113
- sindhi: 5
- south_punjab: 2

## Coverage notes

- Pakistan Food Composition Table files are not bundled. The CSV/JSON importer can load them when a usable file is available.
- Branded restaurant plates and current supermarket prices are not invented.
- Missing nutrients stay empty. They are not stored as zero.
- A food can be verified in the admin screen after a person checks the source.
