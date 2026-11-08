import 'package:flutter/material.dart';

import '../core/theme.dart';

class FitCard extends StatelessWidget {
  const FitCard({super.key, required this.child, this.padding = const EdgeInsets.all(18)});
  final Widget child;
  final EdgeInsets padding;

  @override
  Widget build(BuildContext context) {
    return Card(child: Padding(padding: padding, child: child));
  }
}

class SectionTitle extends StatelessWidget {
  const SectionTitle(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 8, 4, 10),
        child: Text(text, style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
      );
}

class EmptyPane extends StatelessWidget {
  const EmptyPane({super.key, required this.title, this.detail});
  final String title;
  final String? detail;
  @override
  Widget build(BuildContext context) {
    return FitCard(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(Icons.spa_outlined, color: Theme.of(context).colorScheme.primary),
        const SizedBox(height: 8),
        Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
        if (detail != null) ...[const SizedBox(height: 4), Text(detail!, style: TextStyle(color: Theme.of(context).hintColor))],
      ]),
    );
  }
}

class Metric extends StatelessWidget {
  const Metric({super.key, required this.label, required this.value, required this.icon});
  final String label;
  final String value;
  final IconData icon;
  @override
  Widget build(BuildContext context) {
    return FitCard(
      padding: const EdgeInsets.all(14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(icon, color: emerald, size: 20),
        const SizedBox(height: 10),
        Text(value, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
        Text(label, style: TextStyle(color: Theme.of(context).hintColor, fontSize: 12)),
      ]),
    );
  }
}

class MacroLine extends StatelessWidget {
  const MacroLine({super.key, required this.label, required this.value, required this.goal, required this.color});
  final String label;
  final double? value;
  final double? goal;
  final Color color;
  @override
  Widget build(BuildContext context) {
    final progress = (value == null || goal == null || goal == 0) ? null : (value! / goal!).clamp(0, 1).toDouble();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label, style: const TextStyle(fontWeight: FontWeight.w600)),
          const Spacer(),
          Text(value == null ? '—' : '${value!.round()} g'),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(8),
          child: LinearProgressIndicator(
            minHeight: 8,
            value: progress,
            backgroundColor: color.withValues(alpha: 0.15),
            color: color,
          ),
        ),
      ]),
    );
  }
}

String pretty(Object? value, {String suffix = ''}) {
  if (value == null) return '—';
  if (value is num) {
    final text = value == value.roundToDouble() ? value.round().toString() : value.toStringAsFixed(1);
    return '$text$suffix';
  }
  return '$value$suffix';
}
