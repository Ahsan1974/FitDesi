import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class PlanPage extends ConsumerStatefulWidget {
  const PlanPage({super.key});
  @override
  ConsumerState<PlanPage> createState() => _PlanPageState();
}

class _PlanPageState extends ConsumerState<PlanPage> {
  final current = TextEditingController(text: '90');
  final target = TextEditingController(text: '75');
  final height = TextEditingController(text: '170');
  final age = TextEditingController(text: '32');
  Map<String, dynamic>? plan;
  bool busy = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final existing = await ref.read(fitProvider.notifier).currentPlan();
      if (mounted) setState(() => plan = existing);
    });
  }

  @override
  Widget build(BuildContext context) {
    final meals = (plan?['meals'] as List?) ?? [];
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Weight plan', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('Targets use Mifflin–St Jeor and a conservative deficit. A date that is too fast is slowed down. The app does not promise the date.'),
      const SizedBox(height: 12),
      TextField(controller: current, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Current kg')),
      const SizedBox(height: 8),
      TextField(controller: target, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Target kg')),
      const SizedBox(height: 8),
      TextField(controller: height, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Height cm')),
      const SizedBox(height: 8),
      TextField(controller: age, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Age')),
      const SizedBox(height: 12),
      FilledButton(onPressed: busy ? null : _generate, child: Text(busy ? 'Building…' : 'Build a 7-day meal plan')),
      if (plan != null) ...[
        const SizedBox(height: 16),
        FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(plan!['safety_status'].toString(), style: const TextStyle(fontWeight: FontWeight.w800)),
          if (plan!['blocked_reason'] != null) Text(plan!['blocked_reason'].toString()),
          Text('Target ${pretty(plan!['calorie_target'], suffix: ' kcal')} · protein ${pretty(plan!['protein_g'], suffix: ' g')}'),
          if (plan!['coach_note'] != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(plan!['coach_note'].toString())),
        ])),
        for (final day in meals.take(2))
          ...((day as Map)['meals'] as List).map((meal) {
            final row = Map<String, dynamic>.from(meal as Map);
            final lines = (row['items'] as List).map((item) {
              final food = Map<String, dynamic>.from(item as Map);
              return '${food['name']} · ${pretty(food['grams'], suffix: ' g')} · ${pretty(food['energy_kcal'], suffix: ' kcal')}';
            }).join('\n');
            return ListTile(contentPadding: EdgeInsets.zero, title: Text('Day ${day['day_index']} · ${row['meal_type']}'), subtitle: Text(lines));
          }),
      ],
    ]);
  }

  Future<void> _generate() async {
    setState(() => busy = true);
    try {
      final data = await ref.read(fitProvider.notifier).generatePlan({
        'current_weight_kg': double.tryParse(current.text) ?? 80,
        'target_weight_kg': double.tryParse(target.text) ?? 70,
        'height_cm': double.tryParse(height.text) ?? 165,
        'age': int.tryParse(age.text) ?? 30,
        'gender': ref.read(fitProvider).user?['profile']?['gender'] ?? 'unspecified',
        'activity_level': ref.read(fitProvider).user?['profile']?['activity_level'] ?? 'sedentary',
        'days': 7,
        'meals_per_day': 3,
        'diet_type': ref.read(fitProvider).user?['preferences']?['diet_type'] ?? 'non_vegetarian',
      });
      setState(() => plan = data);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}
