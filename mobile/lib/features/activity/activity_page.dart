import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class ActivityPage extends ConsumerStatefulWidget {
  const ActivityPage({super.key});
  @override
  ConsumerState<ActivityPage> createState() => _ActivityPageState();
}

class _ActivityPageState extends ConsumerState<ActivityPage> {
  final steps = TextEditingController();
  final minutes = TextEditingController(text: '30');
  List<dynamic> history = [];
  String? note;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    final rows = await ref.read(fitProvider.notifier).workouts();
    if (mounted) setState(() => history = rows);
  }

  @override
  Widget build(BuildContext context) {
    final dash = ref.watch(fitProvider).dashboard ?? {};
    final selected = dash['steps'] as Map?;
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Movement', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(pretty(selected?['steps']), style: const TextStyle(fontSize: 36, fontWeight: FontWeight.w800)),
        Text('steps today · source ${selected?['source'] ?? 'none yet'}'),
        Text('Target ${pretty(dash['step_target'])}. Distance ${pretty(selected?['distance_m'], suffix: ' m')}.'),
        const SizedBox(height: 8),
        const Text('Health Connect or Apple Health is used when the phone grants access. Manual entry is kept as a separate source and is not added on top.'),
      ])),
      const SizedBox(height: 12),
      FilledButton(onPressed: _health, child: const Text('Read steps from the phone')),
      const SizedBox(height: 8),
      TextField(controller: steps, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Manual steps')),
      const SizedBox(height: 8),
      OutlinedButton(onPressed: () async {
        final message = await ref.read(fitProvider.notifier).saveSteps(int.tryParse(steps.text) ?? 0, 'manual');
        setState(() => note = message);
      }, child: const Text('Save manual steps')),
      const SectionTitle('Workout'),
      TextField(controller: minutes, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Minutes')),
      const SizedBox(height: 8),
      Wrap(spacing: 8, children: [
        for (final kind in ['walking', 'running', 'cycling', 'strength', 'yoga', 'home'])
          ActionChip(label: Text(kind), onPressed: () => _workout(kind)),
      ]),
      if (note != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(note!)),
      const SectionTitle('History'),
      if (history.isEmpty) const EmptyPane(title: 'No workouts yet'),
      ...history.map((raw) {
        final item = Map<String, dynamic>.from(raw as Map);
        return ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text(item['name']?.toString() ?? item['category'].toString()),
          subtitle: Text('${pretty(item['duration_min'], suffix: ' min')} · ${pretty(item['energy_kcal'], suffix: ' kcal estimate')}'),
        );
      }),
    ]);
  }

  Future<void> _health() async {
    final source = Theme.of(context).platform == TargetPlatform.iOS ? 'healthkit' : 'health_connect';
    final count = await ref.read(fitProvider.notifier).readHealthSteps();
    if (!mounted) return;
    if (count == null) {
      setState(() => note = 'Health data is unavailable on this device or permission was declined. Enter steps manually.');
      return;
    }
    final message = await ref.read(fitProvider.notifier).saveSteps(count, source);
    setState(() => note = message ?? 'Synced $count steps from the health platform.');
  }

  Future<void> _workout(String kind) async {
    final message = await ref.read(fitProvider.notifier).saveWorkout({
      'name': kind[0].toUpperCase() + kind.substring(1),
      'category': kind,
      'duration_min': double.tryParse(minutes.text) ?? 30,
      'status': 'completed',
    });
    setState(() => note = message ?? 'Workout saved. The calorie figure is an estimate.');
    await _load();
  }
}
