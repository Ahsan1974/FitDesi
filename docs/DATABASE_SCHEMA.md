# Database schema

The relational model lives in `backend/app/models/entities.py`. Alembic creates the same tables. Primary keys are integers. User-owned rows carry `user_id`. Foods, recipes, users and scans use `deleted_at` for soft deletion.

Groups:

- Identity: `users`, `user_profiles`, `user_preferences`, `user_goals`, `user_allergies`, `user_sessions`, `refresh_tokens`, `auth_tokens`, `consent_records`
- Catalogue: `food_categories`, `regional_cuisines`, `foods`, `food_translations`, `food_aliases`, `food_nutrition`, `food_servings`, `food_sources`, `ingredients`, `recipes`, `recipe_ingredients`, `saved_recipes`, `food_favourites`
- Diary and plans: `daily_food_logs`, `saved_meals`, `saved_meal_items`, `wellness_plans`, `meal_plans`, `meal_plan_versions`, `meal_plan_days`, `meal_plan_meals`, `meal_plan_items`, `workout_plans`, `workout_plan_days`, `plan_adjustments`
- Activity: `exercises`, `daily_steps`, `activity_records`, `workouts`, `workout_exercises`, `weight_entries`, `body_measurements`, `progress_photos`, `water_logs`, `sleep_logs`
- Consultation and AI: `consultant_profiles`, `consultant_credentials`, `consultant_services`, `consultant_availability`, `consultant_bookings`, `consultant_reviews`, `subscriptions`, `payment_records`, `ai_food_scans`, `ai_chat_sessions`, `ai_chat_messages`, `user_feedback`
- Other: `grocery_lists`, `grocery_list_items`, `notifications`, `achievements`, `user_achievements`, `audit_logs`, `application_settings`

`food_nutrition` columns are nullable. A missing vitamin or mineral is SQL NULL, not zero. `daily_steps` is unique per user, day and source. The API then marks one source as selected instead of adding providers together. `daily_food_logs.client_mutation_id` is unique per user so a retried offline sync does not double-log.

`progress_photos` exists for private progress images. The upload route is not implemented yet; do not store those files in the mobile app until that route and deletion control exist.
