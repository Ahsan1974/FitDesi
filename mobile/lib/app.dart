import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'core/text.dart';
import 'core/theme.dart';
import 'features/activity/activity_page.dart';
import 'features/auth/auth_pages.dart';
import 'features/food/food_pages.dart';
import 'features/home/dashboard_page.dart';
import 'features/plans/plan_page.dart';
import 'features/profile/profile_page.dart';
import 'features/progress/progress_page.dart';
import 'state/fit_controller.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(routes: [
    GoRoute(path: '/', builder: (context, state) => const Gate()),
    GoRoute(path: '/scan', builder: (context, state) => const Scaffold(body: SafeArea(child: ScanPage()))),
    GoRoute(path: '/recipe', builder: (context, state) => const Scaffold(appBar: _Bar('Recipe'), body: RecipePage())),
    GoRoute(path: '/plan', builder: (context, state) => const Scaffold(appBar: _Bar('Plan'), body: PlanPage())),
    GoRoute(path: '/chat', builder: (context, state) => const ChatPage()),
    GoRoute(path: '/consultants', builder: (context, state) => const ConsultPage()),
    GoRoute(path: '/grocery', builder: (context, state) => const GroceryPage()),
    GoRoute(path: '/report', builder: (context, state) => const ReportPage()),
  ]);
});

class _Bar extends StatelessWidget implements PreferredSizeWidget {
  const _Bar(this.title);
  final String title;
  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);
  @override
  Widget build(BuildContext context) => AppBar(title: Text(title));
}

class FitApp extends ConsumerWidget {
  const FitApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fit = ref.watch(fitProvider);
    return MaterialApp.router(
      title: 'FitDesi',
      debugShowCheckedModeBanner: false,
      theme: fitTheme(Brightness.light),
      darkTheme: fitTheme(Brightness.dark),
      themeMode: fit.dark ? ThemeMode.dark : ThemeMode.light,
      routerConfig: ref.watch(routerProvider),
      builder: (context, child) => child ?? const SizedBox.shrink(),
    );
  }
}

class Gate extends ConsumerWidget {
  const Gate({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fit = ref.watch(fitProvider);
    if (!fit.ready) {
      return const Scaffold(
        body: Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('FitDesi', style: TextStyle(fontSize: 36, fontWeight: FontWeight.w800, color: emerald)),
            SizedBox(height: 16),
            CircularProgressIndicator(),
          ]),
        ),
      );
    }
    if (!fit.signedIn) return const WelcomePage();
    if (!fit.onboarded) return const OnboardingPage();
    return const HomeShell();
  }
}

class HomeShell extends ConsumerStatefulWidget {
  const HomeShell({super.key});
  @override
  ConsumerState<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends ConsumerState<HomeShell> {
  int index = 0;

  @override
  void initState() {
    super.initState();
    Future.microtask(() => ref.read(fitProvider.notifier).startStepCounter());
  }

  @override
  Widget build(BuildContext context) {
    final locale = ref.watch(fitProvider).locale;
    final pages = [
      DashboardPage(
        onFood: () => setState(() => index = 1),
        onScan: () => context.push('/scan'),
        onWater: () => setState(() => index = 3),
        onWeight: () => setState(() => index = 3),
        onWorkout: () => setState(() => index = 2),
      ),
      const FoodPage(),
      const ActivityPage(),
      const ProgressPage(),
      ProfilePage(open: (route) => context.push(route)),
    ];
    return Scaffold(
      body: SafeArea(child: pages[index]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: index,
        onDestinationSelected: (value) => setState(() => index = value),
        destinations: [
          NavigationDestination(icon: const Icon(Icons.home_outlined), selectedIcon: const Icon(Icons.home), label: tr(locale, 'home')),
          NavigationDestination(icon: const Icon(Icons.restaurant_outlined), selectedIcon: const Icon(Icons.restaurant), label: tr(locale, 'food')),
          NavigationDestination(icon: const Icon(Icons.directions_walk), label: tr(locale, 'activity')),
          NavigationDestination(icon: const Icon(Icons.insights_outlined), selectedIcon: const Icon(Icons.insights), label: tr(locale, 'progress')),
          NavigationDestination(icon: const Icon(Icons.person_outline), selectedIcon: const Icon(Icons.person), label: tr(locale, 'profile')),
        ],
      ),
    );
  }
}
