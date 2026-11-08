# Nutrition calculations

All of the formulas below are in `backend/app/services/calc.py`. Tests in `backend/tests/test_calc.py` lock the examples.

## Portion

`nutrient = nutrient_per_100g × grams / 100`

A food with 250 kcal per 100 g and a 200 g portion is 500 kcal. If the nutrient is NULL, the result is NULL.

## Recipe yield

Ingredient nutrients are scaled to their gram weights and summed. Added water increases cooked weight and adds no nutrients. Water loss reduces cooked weight and concentrates the same nutrient total.

`per_100g_cooked = total_nutrient / cooked_weight_g × 100`

Cooked weight must stay above zero. Raw weight and cooked weight are both stored. An ingredient heavier than 2 g that lacks a nutrient makes that nutrient NULL for the dish. A trace amount at or below 2 g does not.

## Energy expenditure

BMR uses Mifflin–St Jeor, version `v1`.

- Female: `10×kg + 6.25×cm − 5×age − 161`
- Male: `10×kg + 6.25×cm − 5×age + 5`
- Unspecified sex: `10×kg + 6.25×cm − 5×age − 78`

TDEE multiplies BMR by 1.2, 1.375, 1.55, 1.725 or 1.9 for sedentary through extra active.

Activity calories use `MET × kg × hours` and are labelled estimates. They are shown separately and are not added back onto the food budget.

## Weight-loss guardrails

One kilogram of body mass is treated as 7700 kcal for the timeline estimate. The planned loss is capped at the smaller of 1 kg or 1% of body weight per week. Calorie floors are 1500 kcal for male, 1200 for female and 1400 when sex is unspecified. A requested date that would break the cap is extended and the plan status becomes `adjusted`. The response does not promise the original date.

The generator refuses an ordinary deficit when age is under 18, or when pregnancy, breastfeeding, an eating-disorder history, or a non-empty medical-condition note is present. Those responses are `blocked` and contain no meal plan.

Protein is about 1.4 g per kg, limited so it does not dominate the calorie target. Fat is 30% of calories. Carbohydrate fills the rest. Fibre guidance is 30 g. Hydration guidance is 30 ml per kg, clamped between 1800 and 4000 ml, and is labelled guidance rather than a prescription.

The formula name, version, inputs, outputs and timestamp are stored on the wellness plan.
