import 'package:fitdesi/app.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() {
    SharedPreferences.setMockInitialValues({});
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      const MethodChannel('plugins.it_nomads.com/flutter_secure_storage'),
      (call) async => null,
    );
  });

  testWidgets('welcome screen shows the FitDesi name', (tester) async {
    await tester.pumpWidget(const ProviderScope(child: FitApp()));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('FitDesi'), findsWidgets);
    expect(find.text('Sign in'), findsOneWidget);
  });
}
