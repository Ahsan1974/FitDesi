import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/theme.dart';
import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class ProgressPage extends ConsumerStatefulWidget {
  const ProgressPage({super.key});
  @override
  ConsumerState<ProgressPage> createState() => _ProgressPageState();
}

class _ProgressPageState extends ConsumerState<ProgressPage> {
  final weight = TextEditingController();
  final waist = TextEditingController();
  Map<String, dynamic>? history;
  List<dynamic> sleep = [];
  String? note;

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    try {
      final weights = await ref.read(fitProvider.notifier).weightHistory();
      final nights = await ref.read(fitProvider.notifier).sleepHistory();
      if (mounted) setState(() { history = weights; sleep = nights; });
    } catch (error) {
      if (mounted) setState(() => note = error.toString());
    }
  }

  @override
  Widget build(BuildContext context) {
    final points = ((history?['entries'] as List?) ?? []).map((item) => Map<String, dynamic>.from(item as Map)).toList();
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Progress', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('One day’s change is not fat gain or loss. Look at the trend.'),
      const SizedBox(height: 12),
      SizedBox(height: 180, child: points.length < 2 ? const EmptyPane(title: 'Add two weights to see a trend') : _chart(points)),
      const SizedBox(height: 12),
      TextField(controller: weight, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Weight today (kg)')),
      const SizedBox(height: 8),
      FilledButton(onPressed: () async {
        final message = await ref.read(fitProvider.notifier).saveWeight(double.tryParse(weight.text) ?? 0);
        setState(() => note = message);
        await _load();
      }, child: const Text('Save weight')),
      const SectionTitle('Measurements'),
      TextField(controller: waist, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Waist (cm)')),
      const SizedBox(height: 8),
      OutlinedButton(onPressed: () async {
        await ref.read(fitProvider.notifier).api.post('/weight/measurements', data: {'waist_cm': double.tryParse(waist.text)});
        setState(() => note = 'Measurement saved.');
      }, child: const Text('Save waist')),
      const SectionTitle('Water'),
      Wrap(spacing: 8, children: [
        for (final ml in [100, 250, 500])
          ActionChip(label: Text('$ml ml'), onPressed: () async {
            final message = await ref.read(fitProvider.notifier).saveWater(ml);
            setState(() => note = message ?? 'Added $ml ml. This is a personal goal, not a medical prescription.');
          }),
      ]),
      const SectionTitle('Sleep'),
      FilledButton.tonal(onPressed: () async {
        final now = DateTime.now();
        final message = await ref.read(fitProvider.notifier).saveSleep(now.subtract(const Duration(hours: 7)), now);
        setState(() => note = message ?? 'Logged 7 hours as a manual entry.');
        await _load();
      }, child: const Text('Log last 7 hours')),
      if (sleep.isNotEmpty) Text('${sleep.length} sleep records. Manual and imported records stay labelled by source.'),
      if (note != null) Padding(padding: const EdgeInsets.only(top: 12), child: Text(note!)),
    ]);
  }

  Widget _chart(List<Map<String, dynamic>> points) {
    final spots = <FlSpot>[];
    for (var i = 0; i < points.length; i++) {
      final value = points[i]['weight_kg'];
      if (value is num) spots.add(FlSpot(i.toDouble(), value.toDouble()));
    }
    return FitCard(child: LineChart(LineChartData(
      gridData: const FlGridData(show: false),
      titlesData: const FlTitlesData(show: false),
      borderData: FlBorderData(show: false),
      lineBarsData: [LineChartBarData(spots: spots, isCurved: true, color: emerald, barWidth: 3, dotData: const FlDotData(show: false))],
    )));
  }
}
