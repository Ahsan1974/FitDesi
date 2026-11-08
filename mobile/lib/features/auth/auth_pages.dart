import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../core/text.dart';
import '../../state/fit_controller.dart';

class WelcomePage extends ConsumerStatefulWidget {
  const WelcomePage({super.key});
  @override
  ConsumerState<WelcomePage> createState() => _WelcomePageState();
}

class _WelcomePageState extends ConsumerState<WelcomePage> {
  final email = TextEditingController();
  final password = TextEditingController();
  final name = TextEditingController();
  final server = TextEditingController();
  bool create = false;
  String? message;

  @override
  void dispose() {
    email.dispose();
    password.dispose();
    name.dispose();
    server.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final fit = ref.watch(fitProvider);
    if (server.text.isEmpty) server.text = fit.baseUrl;
    final locale = fit.locale;
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(colors: [emeraldDeep, emerald], begin: Alignment.topLeft, end: Alignment.bottomRight),
        ),
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(22),
            children: [
              const SizedBox(height: 28),
              Container(
                width: 64,
                height: 64,
                alignment: Alignment.center,
                decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.16), borderRadius: BorderRadius.circular(20)),
                child: const Text('ف', style: TextStyle(color: Colors.white, fontSize: 32, fontWeight: FontWeight.w800)),
              ),
              const SizedBox(height: 18),
              Text(tr(locale, 'app'), style: const TextStyle(color: Colors.white, fontSize: 40, fontWeight: FontWeight.w800)),
              const SizedBox(height: 6),
              Text(tr(locale, 'tagline'), style: TextStyle(color: Colors.white.withValues(alpha: 0.86), fontSize: 16)),
              const SizedBox(height: 28),
              Material(
                color: Colors.white,
                borderRadius: BorderRadius.circular(28),
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(children: [
                    if (create) TextField(controller: name, decoration: InputDecoration(labelText: tr(locale, 'name'))),
                    if (create) const SizedBox(height: 10),
                    TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: InputDecoration(labelText: tr(locale, 'email'))),
                    const SizedBox(height: 10),
                    TextField(controller: password, obscureText: true, decoration: InputDecoration(labelText: tr(locale, 'password'))),
                    const SizedBox(height: 10),
                    TextField(controller: server, decoration: InputDecoration(labelText: tr(locale, 'server'), hintText: 'http://192.168.1.8:8000')),
                    if (message != null) ...[
                      const SizedBox(height: 10),
                      Text(message!, style: TextStyle(color: message == tr(locale, 'offline') ? emerald : Colors.red.shade700)),
                    ],
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: fit.busy ? null : _submit,
                      child: Text(fit.busy ? '…' : (create ? tr(locale, 'register') : tr(locale, 'login'))),
                    ),
                    TextButton(
                      onPressed: () => setState(() => create = !create),
                      child: Text(create ? tr(locale, 'login') : tr(locale, 'register')),
                    ),
                    TextButton(onPressed: _forgot, child: const Text('Forgot password')),
                  ]),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _submit() async {
    final controller = ref.read(fitProvider.notifier);
    await controller.setBaseUrl(server.text);
    final error = create
        ? await controller.register(name.text.trim(), email.text.trim(), password.text)
        : await controller.login(email.text.trim(), password.text);
    if (mounted) setState(() => message = error);
  }

  Future<void> _forgot() async {
    final note = await ref.read(fitProvider.notifier).forgot(email.text.trim());
    if (mounted) setState(() => message = note);
  }
}

class OnboardingPage extends ConsumerStatefulWidget {
  const OnboardingPage({super.key});
  @override
  ConsumerState<OnboardingPage> createState() => _OnboardingPageState();
}

class _OnboardingPageState extends ConsumerState<OnboardingPage> {
  final page = PageController();
  int index = 0;
  final name = TextEditingController();
  final height = TextEditingController(text: '165');
  final weight = TextEditingController(text: '78');
  final target = TextEditingController(text: '68');
  final budget = TextEditingController(text: '800');
  String gender = 'female';
  String activity = 'lightly_active';
  String diet = 'non_vegetarian';
  bool health = false;
  bool ai = false;
  String? error;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Step ${index + 1} of 3')),
      body: PageView(
        controller: page,
        onPageChanged: (value) => setState(() => index = value),
        children: [
          _step([
            const Text('Tell FitDesi who the plan is for.', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            const SizedBox(height: 16),
            TextField(controller: name, decoration: const InputDecoration(labelText: 'Full name')),
            const SizedBox(height: 10),
            DropdownButtonFormField(initialValue: gender, items: const [
              DropdownMenuItem(value: 'female', child: Text('Female')),
              DropdownMenuItem(value: 'male', child: Text('Male')),
              DropdownMenuItem(value: 'unspecified', child: Text('Prefer not to say')),
            ], onChanged: (value) => setState(() => gender = value ?? gender)),
          ]),
          _step([
            const Text('Body and daily life', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            const SizedBox(height: 16),
            TextField(controller: height, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Height (cm)')),
            const SizedBox(height: 10),
            TextField(controller: weight, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Current weight (kg)')),
            const SizedBox(height: 10),
            TextField(controller: target, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Target weight (kg)')),
            const SizedBox(height: 10),
            DropdownButtonFormField(initialValue: activity, items: const [
              DropdownMenuItem(value: 'sedentary', child: Text('Sedentary')),
              DropdownMenuItem(value: 'lightly_active', child: Text('Lightly active')),
              DropdownMenuItem(value: 'moderately_active', child: Text('Moderately active')),
              DropdownMenuItem(value: 'very_active', child: Text('Very active')),
              DropdownMenuItem(value: 'extra_active', child: Text('Extra active')),
            ], onChanged: (value) => setState(() => activity = value ?? activity)),
          ]),
          _step([
            const Text('Food and consent', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            const Text('Pakistani meals stay in the plan. Nothing here is medical advice.'),
            const SizedBox(height: 12),
            DropdownButtonFormField(initialValue: diet, items: const [
              DropdownMenuItem(value: 'non_vegetarian', child: Text('Non-vegetarian')),
              DropdownMenuItem(value: 'vegetarian', child: Text('Vegetarian')),
              DropdownMenuItem(value: 'vegan', child: Text('Vegan')),
            ], onChanged: (value) => setState(() => diet = value ?? diet)),
            const SizedBox(height: 10),
            TextField(controller: budget, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Daily food budget (PKR)')),
            CheckboxListTile(value: health, onChanged: (value) => setState(() => health = value ?? false), title: const Text('Allow health data such as steps'), contentPadding: EdgeInsets.zero),
            CheckboxListTile(value: ai, onChanged: (value) => setState(() => ai = value ?? false), title: const Text('Allow AI to use my records when I ask'), contentPadding: EdgeInsets.zero),
            if (error != null) Text(error!, style: TextStyle(color: Colors.red.shade700)),
          ]),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton(onPressed: _next, child: Text(index == 2 ? 'Finish' : 'Continue')),
        ),
      ),
    );
  }

  Widget _step(List<Widget> children) => ListView(padding: const EdgeInsets.all(20), children: children);

  Future<void> _next() async {
    if (index < 2) {
      page.nextPage(duration: const Duration(milliseconds: 280), curve: Curves.easeOut);
      return;
    }
    final message = await ref.read(fitProvider.notifier).onboard({
      'full_name': name.text.trim(),
      'gender': gender,
      'height_cm': double.tryParse(height.text) ?? 165,
      'current_weight_kg': double.tryParse(weight.text) ?? 70,
      'target_weight_kg': double.tryParse(target.text) ?? 65,
      'activity_level': activity,
      'diet_type': diet,
      'daily_food_budget_pkr': double.tryParse(budget.text),
      'meals_per_day': 3,
      'consent_health': health,
      'consent_ai': ai,
      'timezone': 'Asia/Karachi',
      'currency': 'PKR',
    });
    if (mounted) setState(() => error = message);
  }
}
