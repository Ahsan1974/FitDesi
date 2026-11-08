import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/theme.dart';
import '../../state/fit_controller.dart';
import '../../widgets/common.dart';

class FoodPage extends ConsumerStatefulWidget {
  const FoodPage({super.key});
  @override
  ConsumerState<FoodPage> createState() => _FoodPageState();
}

class _FoodPageState extends ConsumerState<FoodPage> {
  final query = TextEditingController();
  List<Map<String, dynamic>> results = [];
  Map<String, dynamic>? diary;
  bool loading = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(_loadDiary);
  }

  Future<void> _loadDiary() async {
    final data = await ref.read(fitProvider.notifier).diary();
    if (mounted) setState(() => diary = data);
  }

  Future<void> _search(String value) async {
    setState(() => loading = true);
    final items = await ref.read(fitProvider.notifier).searchFoods(value);
    if (mounted) setState(() { results = items; loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    final items = (diary?['items'] as List?) ?? [];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        TextField(
          controller: query,
          decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search biryani, چکن, roti'),
          onSubmitted: _search,
        ),
        const SizedBox(height: 8),
        if (loading) const LinearProgressIndicator(minHeight: 3),
        ...results.map((food) => ListTile(
              contentPadding: EdgeInsets.zero,
              title: Text(food['name_en'].toString(), style: const TextStyle(fontWeight: FontWeight.w700)),
              subtitle: Text('${food['name_ur'] ?? ''} · ${pretty((food['per_100g'] as Map?)?['energy_kcal'], suffix: ' kcal/100g')} · ${food['data_origin']}'),
              trailing: const Icon(Icons.add_circle, color: emerald),
              onTap: () => _log(food),
            )),
        const SectionTitle('Today'),
        if (items.isEmpty) const EmptyPane(title: 'No meals logged', detail: 'Search a Pakistani dish and add a portion.'),
        ...items.map((raw) {
          final item = Map<String, dynamic>.from(raw as Map);
          return FitCard(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: ListTile(
              title: Text(item['custom_name']?.toString() ?? 'Food'),
              subtitle: Text('${item['meal_type']} · ${pretty(item['grams'], suffix: ' g')} · ${pretty(item['energy_kcal'], suffix: ' kcal')}'),
              trailing: IconButton(icon: const Icon(Icons.delete_outline), onPressed: () async {
                await ref.read(fitProvider.notifier).deleteDiary(item['id'] as int);
                await _loadDiary();
              }),
            ),
          );
        }),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: () async { await ref.read(fitProvider.notifier).copyYesterday(); await _loadDiary(); }, child: const Text('Copy yesterday')),
      ],
    );
  }

  Future<void> _log(Map<String, dynamic> food) async {
    final grams = TextEditingController(text: '${food['default_serving_g'] ?? 100}');
    String meal = 'lunch';
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (context) => Padding(
        padding: EdgeInsets.fromLTRB(16, 0, 16, 16 + MediaQuery.viewInsetsOf(context).bottom),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(food['name_en'].toString(), style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          if (food['nutrition_note'] != null) Text(food['nutrition_note'].toString(), style: TextStyle(color: Theme.of(context).hintColor)),
          const SizedBox(height: 10),
          TextField(controller: grams, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Grams')),
          const SizedBox(height: 10),
          DropdownButtonFormField<String>(initialValue: meal, items: const [
            DropdownMenuItem(value: 'breakfast', child: Text('Breakfast')),
            DropdownMenuItem(value: 'morning_snack', child: Text('Morning snack')),
            DropdownMenuItem(value: 'lunch', child: Text('Lunch')),
            DropdownMenuItem(value: 'afternoon_snack', child: Text('Afternoon snack')),
            DropdownMenuItem(value: 'dinner', child: Text('Dinner')),
            DropdownMenuItem(value: 'evening_snack', child: Text('Evening snack')),
          ], onChanged: (value) => meal = value ?? meal),
          const SizedBox(height: 12),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Add to diary')),
        ]),
      ),
    );
    if (ok == true) {
      final note = await ref.read(fitProvider.notifier).logFood({'food_id': food['id'], 'grams': double.tryParse(grams.text) ?? 100, 'meal_type': meal});
      if (mounted && note == 'offline') ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Saved on this phone until the server is reachable.')));
      await _loadDiary();
    }
  }
}

class ScanPage extends ConsumerStatefulWidget {
  const ScanPage({super.key});
  @override
  ConsumerState<ScanPage> createState() => _ScanPageState();
}

class _ScanPageState extends ConsumerState<ScanPage> {
  Map<String, dynamic>? result;
  bool busy = false;

  Future<void> _pick(ImageSource source) async {
    final file = await ImagePicker().pickImage(source: source, imageQuality: 70, maxWidth: 1280);
    if (file == null) return;
    setState(() => busy = true);
    try {
      final data = await ref.read(fitProvider.notifier).scan(file.path);
      if (mounted) setState(() => result = data);
    } catch (error) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(error.toString())));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final predictions = (result?['predictions'] as List?) ?? [];
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Scan a meal', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('A photo can suggest a dish. It cannot see oil, ghee or hidden ingredients. You confirm before anything is logged.'),
      const SizedBox(height: 16),
      Row(children: [
        Expanded(child: FilledButton.icon(onPressed: busy ? null : () => _pick(ImageSource.camera), icon: const Icon(Icons.photo_camera_outlined), label: const Text('Camera'))),
        const SizedBox(width: 8),
        Expanded(child: OutlinedButton.icon(onPressed: busy ? null : () => _pick(ImageSource.gallery), icon: const Icon(Icons.photo_outlined), label: const Text('Library'))),
      ]),
      if (busy) const Padding(padding: EdgeInsets.all(16), child: LinearProgressIndicator()),
      if (result != null) ...[
        const SizedBox(height: 16),
        FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(result!['status'].toString().replaceAll('_', ' '), style: const TextStyle(fontWeight: FontWeight.w800)),
          const SizedBox(height: 6),
          Text(result!['message']?.toString() ?? 'Estimate only.'),
        ])),
        if (predictions.isEmpty) const Padding(padding: EdgeInsets.only(top: 12), child: EmptyPane(title: 'No food was identified', detail: 'Search and log the meal yourself. Nothing was saved.')),
        ...predictions.map((raw) {
          final item = Map<String, dynamic>.from(raw as Map);
          return ListTile(
            title: Text(item['matched_name']?.toString() ?? item['name'].toString()),
            subtitle: const Text('Estimate · confirm the portion'),
            trailing: item['food_id'] == null ? null : FilledButton(onPressed: () => _confirm(item), child: const Text('Confirm')),
          );
        }),
        if (result?['scan_id'] != null)
          TextButton(onPressed: () async {
            await ref.read(fitProvider.notifier).deleteScan(result!['scan_id'] as int);
            setState(() => result = null);
          }, child: const Text('Delete this photo')),
      ],
    ]);
  }

  Future<void> _confirm(Map item) async {
    await ref.read(fitProvider.notifier).logFood({'food_id': item['food_id'], 'grams': 200, 'meal_type': 'lunch', 'scan_id': result?['scan_id']});
    if (mounted) Navigator.pop(context);
  }
}

class RecipePage extends ConsumerStatefulWidget {
  const RecipePage({super.key});
  @override
  ConsumerState<RecipePage> createState() => _RecipePageState();
}

class _RecipePageState extends ConsumerState<RecipePage> {
  final rows = <TextEditingController>[TextEditingController(text: 'chicken'), TextEditingController(), TextEditingController()];
  final grams = <TextEditingController>[TextEditingController(text: '500'), TextEditingController(text: '30'), TextEditingController(text: '200')];
  final loss = TextEditingController(text: '80');
  Map<String, dynamic>? result;

  @override
  Widget build(BuildContext context) {
    final per = result?['per_100g'] as Map?;
    return ListView(padding: const EdgeInsets.all(16), children: [
      const Text('Recipe calculator', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('Cooked weight is not treated as the same as raw weight. Water loss changes the calories per 100 g.'),
      const SizedBox(height: 12),
      for (var i = 0; i < rows.length; i++)
        Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(children: [
            Expanded(flex: 2, child: TextField(controller: rows[i], decoration: const InputDecoration(labelText: 'Ingredient search'))),
            const SizedBox(width: 8),
            Expanded(child: TextField(controller: grams[i], keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Grams'))),
          ]),
        ),
      TextField(controller: loss, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Water lost in cooking (g)')),
      const SizedBox(height: 12),
      FilledButton(onPressed: _calc, child: const Text('Calculate')),
      if (per != null) ...[
        const SizedBox(height: 12),
        FitCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('${pretty(per['energy_kcal'])} kcal per 100 g cooked', style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800)),
          Text('Protein ${pretty(per['protein_g'])} g · Carbs ${pretty(per['carbohydrate_g'])} g · Fat ${pretty(per['fat_g'])} g'),
          Text('Raw ${pretty(result?['raw_weight_g'], suffix: ' g')} · Cooked ${pretty(result?['cooked_weight_g'], suffix: ' g')}'),
          const SizedBox(height: 6),
          const Text('This is a calculated estimate from the ingredient records.'),
        ])),
      ],
    ]);
  }

  Future<void> _calc() async {
    final ingredients = <Map<String, dynamic>>[];
    for (var i = 0; i < rows.length; i++) {
      if (rows[i].text.trim().isEmpty) continue;
      final matches = await ref.read(fitProvider.notifier).searchFoods(rows[i].text.trim());
      if (matches.isEmpty) continue;
      ingredients.add({'food_id': matches.first['id'], 'grams': double.tryParse(grams[i].text) ?? 0});
    }
    if (ingredients.isEmpty) return;
    final data = await ref.read(fitProvider.notifier).calculateRecipe(ingredients, double.tryParse(loss.text) ?? 0, 4);
    if (mounted) setState(() => result = data);
  }
}
