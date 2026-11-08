import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/text.dart';
import '../../core/theme.dart';
import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key, required this.onFood, required this.onScan, required this.onWater, required this.onWeight, required this.onWorkout});
  final VoidCallback onFood;
  final VoidCallback onScan;
  final VoidCallback onWater;
  final VoidCallback onWeight;
  final VoidCallback onWorkout;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fit = ref.watch(fitProvider);
    final dash = fit.dashboard ?? {};
    final macros = (dash['macros'] as Map?) ?? {};
    final logged = macros['logged'] == true;
    return RefreshIndicator(
      onRefresh: () => ref.read(fitProvider.notifier).refreshDashboard(),
      child: ListView(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
        children: [
          Text('Hello Ahsan', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800)),
          Text(tr(fit.locale, 'tagline'), style: TextStyle(color: Theme.of(context).hintColor)),
          if (fit.dashboardLoading) const Padding(padding: EdgeInsets.only(top: 12), child: LinearProgressIndicator(minHeight: 3)),
          if (fit.loadError != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(fit.loadError!, style: const TextStyle(color: Color(0xFF9D2C2C)))),
          const SizedBox(height: 16),
          FitCard(
            child: Row(children: [
              _ring(dash['calories_consumed'], dash['calorie_target']),
              const SizedBox(width: 16),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(tr(fit.locale, 'consumed'), style: const TextStyle(fontWeight: FontWeight.w600)),
                Text(logged ? pretty(dash['calories_consumed'], suffix: ' kcal') : 'Not logged', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text('${tr(fit.locale, 'target')} ${pretty(dash['calorie_target'], suffix: ' kcal')}'),
                Text('${tr(fit.locale, 'remaining')} ${pretty(dash['remaining'], suffix: ' kcal')}'),
              ])),
            ]),
          ),
          const SizedBox(height: 12),
          FitCard(child: Column(children: [
            MacroLine(label: 'Protein', value: _num(macros['protein_g']), goal: _num(fit.user?['goals']?['protein_g']), color: emerald),
            MacroLine(label: 'Carbs', value: _num(macros['carbohydrate_g']), goal: _num(fit.user?['goals']?['carbohydrate_g']), color: const Color(0xFFE0A106)),
            MacroLine(label: 'Fat', value: _num(macros['fat_g']), goal: _num(fit.user?['goals']?['fat_g']), color: const Color(0xFFD46A4C)),
            MacroLine(label: 'Fibre', value: _num(macros['fibre_g']), goal: _num(fit.user?['goals']?['fibre_g']) ?? 30, color: const Color(0xFF3C8D6E)),
          ])),
          const SizedBox(height: 12),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 10,
            crossAxisSpacing: 10,
            childAspectRatio: 1.45,
            children: [
              Metric(label: tr(fit.locale, 'steps'), value: pretty(_steps(fit, dash)), icon: Icons.directions_walk),
              Metric(label: tr(fit.locale, 'water'), value: pretty(dash['water_ml'], suffix: ' ml'), icon: Icons.water_drop_outlined),
              Metric(label: tr(fit.locale, 'weight'), value: pretty(dash['targets']?['current_weight_kg'], suffix: ' kg'), icon: Icons.monitor_weight_outlined),
              Metric(label: 'Exercise', value: pretty(dash['expenditure']?['active_exercise_kcal'], suffix: ' kcal'), icon: Icons.local_fire_department_outlined),
            ],
          ),
          const SizedBox(height: 8),
          Text('Exercise calories stay separate from the food budget.', style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12)),
          const SectionTitle('Quick actions'),
          Wrap(spacing: 8, runSpacing: 8, children: [
            ActionChip(avatar: const Icon(Icons.add, size: 18), label: Text(tr(fit.locale, 'addFood')), onPressed: onFood),
            ActionChip(avatar: const Icon(Icons.document_scanner_outlined, size: 18), label: Text(tr(fit.locale, 'scan')), onPressed: onScan),
            ActionChip(avatar: const Icon(Icons.water_drop_outlined, size: 18), label: Text(tr(fit.locale, 'water')), onPressed: onWater),
            ActionChip(avatar: const Icon(Icons.monitor_weight_outlined, size: 18), label: Text(tr(fit.locale, 'weight')), onPressed: onWeight),
            ActionChip(avatar: const Icon(Icons.fitness_center, size: 18), label: Text(tr(fit.locale, 'workout')), onPressed: onWorkout),
          ]),
          if (fit.stepNote != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(fit.stepNote!)),
          const SizedBox(height: 12),
          const _CoachTip(),
          if (dash['plan'] != null) ...[
            const SectionTitle('Active plan'),
            FitCard(child: Text('Calorie target ${pretty(dash['plan']['calorie_target'], suffix: ' kcal')} · ${dash['plan']['safety_status']}')),
          ],
          if (!logged) ...[const SizedBox(height: 12), EmptyPane(title: tr(fit.locale, 'emptyDay'), detail: 'A missing day is not counted as zero.')],
        ],
      ),
    );
  }

  int _steps(FitState fit, Map dash) {
    final server = dash['steps']?['steps'];
    final serverSteps = server is num ? server.toInt() : 0;
    return fit.liveSteps > serverSteps ? fit.liveSteps : serverSteps;
  }

  double? _num(Object? value) => value is num ? value.toDouble() : null;

  Widget _ring(Object? eaten, Object? target) {
    final goal = target is num && target > 0 ? target.toDouble() : null;
    final value = eaten is num ? eaten.toDouble() : 0.0;
    final fraction = goal == null ? 0.0 : (value / goal).clamp(0, 1).toDouble();
    return SizedBox(
      width: 108,
      height: 108,
      child: Stack(alignment: Alignment.center, children: [
        PieChart(PieChartData(sectionsSpace: 0, centerSpaceRadius: 36, startDegreeOffset: -90, sections: [
          PieChartSectionData(value: fraction == 0 ? 0.001 : fraction, color: emerald, radius: 12, showTitle: false),
          PieChartSectionData(value: 1 - fraction, color: mint, radius: 12, showTitle: false),
        ])),
        Text(goal == null ? '—' : '${(fraction * 100).round()}%', style: const TextStyle(fontWeight: FontWeight.w800)),
      ]),
    );
  }
}

class _CoachTip extends ConsumerStatefulWidget {
  const _CoachTip();
  @override
  ConsumerState<_CoachTip> createState() => _CoachTipState();
}

class _CoachTipState extends ConsumerState<_CoachTip> {
  String? tip;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    try {
      final text = await ref.read(fitProvider.notifier).dailyTip();
      if (mounted) setState(() { tip = text; loading = false; });
    } catch (_) {
      if (mounted) setState(() { tip = 'Log a meal and your coach can use today\'s numbers.'; loading = false; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Coach', style: TextStyle(fontWeight: FontWeight.w800)),
      const SizedBox(height: 6),
      if (loading) const LinearProgressIndicator(minHeight: 3) else Text(tip ?? ''),
    ]));
  }
}
