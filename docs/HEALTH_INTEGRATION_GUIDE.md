# Health integration

The Flutter app uses the `health` package.

- Android 8 and newer (`minSdk 26`). Permissions in the manifest cover activity recognition, Health Connect steps, distance and sleep. The Health Connect permission-usage activity alias is declared. Install Health Connect on the phone. The app requests step permission when the user taps "Read steps from the phone".
- iOS: `NSHealthShareUsageDescription` and `NSHealthUpdateUsageDescription` are in `Info.plist`. A physical iPhone and a signing team are required. This workspace cannot run that test.
- If the platform returns nothing, or the permission is declined, the screen tells the user to enter steps manually.
- `POST /activity/steps/sync` stores one row per source per day. The higher-priority source is selected: Health Connect or HealthKit, then a device sensor, then manual. Sources are not added together.
- Distance and duration on the dashboard come from that selected row. Walking estimates use a 0.75 m stride and a 100 steps-per-minute cadence when the platform did not send distance.
- Sleep can be typed in the app (`source=manual`). A Health Connect or HealthKit sleep import can use the same endpoint with its own source string. The history keeps that label.
- Background step counting was not tested on a device. Do not describe it as continuous until it has been checked on hardware with the screen off.

Local notifications are available through `flutter_local_notifications`. Exact quiet-hour scheduling still needs a device pass. Preference flags and quiet-hour fields are stored on `user_preferences`.
