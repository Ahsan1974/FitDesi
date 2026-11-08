import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class ProfilePage extends ConsumerWidget {
  const ProfilePage({super.key, required this.open});
  final void Function(String route) open;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final fit = ref.watch(fitProvider);
    final user = fit.user ?? {};
    return ListView(padding: const EdgeInsets.all(16), children: [
      Text(user['full_name']?.toString() ?? 'Profile', style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      Text(user['email']?.toString() ?? ''),
      const SizedBox(height: 12),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('Dark mode'),
        value: fit.dark,
        onChanged: (value) => ref.read(fitProvider.notifier).setDark(value),
      ),
      SwitchListTile(
        contentPadding: EdgeInsets.zero,
        title: const Text('اردو'),
        value: fit.locale == 'ur',
        onChanged: (value) => ref.read(fitProvider.notifier).setLocale(value ? 'ur' : 'en'),
      ),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Weight-loss plan'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/plan')),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Recipe calculator'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/recipe')),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Nutrition consultant'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/chat')),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Dietitian booking'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/consultants')),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Grocery list'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/grocery')),
      ListTile(contentPadding: EdgeInsets.zero, title: const Text('Weekly report'), trailing: const Icon(Icons.chevron_right), onTap: () => open('/report')),
      ListTile(
        contentPadding: EdgeInsets.zero,
        title: Text('Sync ${fit.pending} pending entries'),
        onTap: () => ref.read(fitProvider.notifier).syncOutbox(),
      ),
      const SizedBox(height: 8),
      OutlinedButton(onPressed: () => ref.read(fitProvider.notifier).logout(), child: const Text('Log out')),
      TextButton(
        onPressed: () async {
          final yes = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
            title: const Text('Delete account?'),
            content: const Text('Your login will be anonymised. This cannot be undone from the app.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
              TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
            ],
          ));
          if (yes == true) await ref.read(fitProvider.notifier).deleteAccount();
        },
        child: const Text('Delete account'),
      ),
      const FitCard(child: Text('Asia/Karachi and PKR are the defaults. Health photos and AI use only the consent you gave.')),
    ]);
  }
}

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});
  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final input = TextEditingController();
  final messages = <(bool, String)>[];
  int? sessionId;
  bool busy = false;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Consultant')),
      body: Column(children: [
        const Padding(padding: EdgeInsets.all(12), child: Text('Answers use your logged records. This is not a diagnosis and not a diet prescription.')),
        Expanded(child: ListView(padding: const EdgeInsets.all(12), children: [
          for (final message in messages)
            Align(
              alignment: message.$1 ? Alignment.centerRight : Alignment.centerLeft,
              child: Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                constraints: const BoxConstraints(maxWidth: 320),
                decoration: BoxDecoration(color: message.$1 ? const Color(0xFFD8F6E8) : Colors.white, borderRadius: BorderRadius.circular(16)),
                child: Text(message.$2),
              ),
            ),
        ])),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(children: [
            Expanded(child: TextField(controller: input, decoration: const InputDecoration(hintText: 'Can I eat biryani while losing weight?'))),
            const SizedBox(width: 8),
            IconButton(onPressed: busy ? null : _send, icon: const Icon(Icons.send)),
          ]),
        ),
      ]),
    );
  }

  Future<void> _send() async {
    final text = input.text.trim();
    if (text.isEmpty) return;
    input.clear();
    setState(() { messages.add((true, text)); busy = true; });
    try {
      final reply = await ref.read(fitProvider.notifier).chat(text, sessionId: sessionId);
      setState(() => messages.add((false, reply)));
    } catch (error) {
      setState(() => messages.add((false, error.toString())));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

class ConsultPage extends ConsumerStatefulWidget {
  const ConsultPage({super.key});
  @override
  ConsumerState<ConsultPage> createState() => _ConsultPageState();
}

class _ConsultPageState extends ConsumerState<ConsultPage> {
  List<dynamic> people = [];
  String? note;

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final rows = await ref.read(fitProvider.notifier).consultants();
      if (mounted) setState(() => people = rows);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dietitians')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Fees shown here are the amounts an administrator entered. An unverified profile is not a confirmed professional, and no payment is taken until a merchant account is configured.'),
        const SizedBox(height: 12),
        if (people.isEmpty) const EmptyPane(title: 'No consultants are published'),
        for (final raw in people)
          _card(Map<String, dynamic>.from(raw as Map)),
        if (note != null) Text(note!),
      ]),
    );
  }

  Widget _card(Map<String, dynamic> person) {
    final services = (person['services'] as List?) ?? [];
    return FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(person['display_name'].toString(), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18)),
      Text('${person['verification_status']} · ${person['specialization'] ?? ''}'),
      if (person['fee_disclaimer'] != null) Text(person['fee_disclaimer'].toString()),
      for (final raw in services)
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: Text((raw as Map)['title'].toString()),
          subtitle: Text('${raw['price_amount']} ${raw['currency']} · ${raw['price_source']} · ${raw['duration_min']} min'),
          trailing: TextButton(onPressed: () async {
            final message = await ref.read(fitProvider.notifier).book(person['id'] as int, raw['id'] as int, DateTime.now().add(const Duration(days: 2)));
            setState(() => note = message ?? 'Requested. Payment status stays not configured until a real provider is connected.');
          }, child: const Text('Request')),
        ),
    ]));
  }
}

class GroceryPage extends ConsumerStatefulWidget {
  const GroceryPage({super.key});
  @override
  ConsumerState<GroceryPage> createState() => _GroceryPageState();
}

class _GroceryPageState extends ConsumerState<GroceryPage> {
  List<dynamic> lists = [];

  @override
  void initState() {
    super.initState();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    final rows = await ref.read(fitProvider.notifier).grocery();
    if (mounted) setState(() => lists = rows);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Grocery')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        const Text('Prices stay blank until you type them. FitDesi does not invent supermarket prices.'),
        const SizedBox(height: 12),
        FilledButton(onPressed: () async {
          final plan = await ref.read(fitProvider.notifier).currentPlan();
          await ref.read(fitProvider.notifier).createGrocery(plan?['meal_plan_id'] as int?);
          await _load();
        }, child: const Text('Build a list from the meal plan')),
        for (final raw in lists) _list(Map<String, dynamic>.from(raw as Map)),
      ]),
    );
  }

  Widget _list(Map<String, dynamic> list) {
    final items = (list['items'] as List?) ?? [];
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SectionTitle(list['name'].toString()),
      for (final raw in items)
        CheckboxListTile(
          value: (raw as Map)['purchased'] == true,
          title: Text(raw['name'].toString()),
          subtitle: Text('${pretty(raw['quantity_g'], suffix: ' g')}${raw['price_amount'] == null ? '' : ' · ${raw['price_amount']} ${raw['currency']} (${raw['price_source']})'}'),
          onChanged: (value) async {
            await ref.read(fitProvider.notifier).updateGrocery(list['id'] as int, {'name': list['name'], 'budget_pkr': list['budget_pkr'], 'items': [{'id': raw['id'], 'purchased': value}]});
            await _load();
          },
        ),
    ]);
  }
}

class ReportPage extends ConsumerStatefulWidget {
  const ReportPage({super.key});
  @override
  ConsumerState<ReportPage> createState() => _ReportPageState();
}

class _ReportPageState extends ConsumerState<ReportPage> {
  Map<String, dynamic>? report;
  String? csv;

  @override
  void initState() {
    super.initState();
    Future.microtask(() async {
      final data = await ref.read(fitProvider.notifier).weeklyReport();
      if (mounted) setState(() => report = data);
    });
  }

  @override
  Widget build(BuildContext context) {
    final days = (report?['days'] as List?) ?? [];
    return Scaffold(
      appBar: AppBar(title: const Text('Weekly report')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text('Logged days: ${report?['days_with_logs'] ?? '—'}', style: const TextStyle(fontWeight: FontWeight.w800)),
        const Text('Days without a food log are missing, not zero.'),
        const SizedBox(height: 8),
        for (final raw in days)
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text((raw as Map)['date'].toString()),
            trailing: Text(raw['logged'] == true ? pretty(raw['energy_kcal'], suffix: ' kcal') : 'No log'),
          ),
        FilledButton(onPressed: () async {
          final text = await ref.read(fitProvider.notifier).exportCsv();
          setState(() => csv = text);
        }, child: const Text('Load CSV')),
        if (csv != null) SelectableText(csv!),
      ]),
    );
  }
}
