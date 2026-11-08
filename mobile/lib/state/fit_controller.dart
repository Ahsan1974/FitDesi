import 'dart:async';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:health/health.dart';
import 'package:pedometer/pedometer.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../core/api.dart';
import '../core/local_store.dart';

class FitState {
  const FitState({
    this.ready = false,
    this.busy = false,
    this.user,
    this.dashboard,
    this.locale = 'en',
    this.dark = false,
    this.baseUrl = kApiBase,
    this.notice,
    this.pending = 0,
    this.liveSteps = 0,
    this.stepNote,
    this.dashboardLoading = false,
    this.loadError,
  });

  final bool ready;
  final bool busy;
  final Map<String, dynamic>? user;
  final Map<String, dynamic>? dashboard;
  final String locale;
  final bool dark;
  final String baseUrl;
  final String? notice;
  final int pending;
  final int liveSteps;
  final String? stepNote;
  final bool dashboardLoading;
  final String? loadError;

  bool get signedIn => user != null;
  bool get onboarded => user?['profile']?['onboarding_completed'] == true;

  FitState copy({
    bool? ready,
    bool? busy,
    Map<String, dynamic>? user,
    bool clearUser = false,
    Map<String, dynamic>? dashboard,
    String? locale,
    bool? dark,
    String? baseUrl,
    String? notice,
    bool clearNotice = false,
    int? pending,
    int? liveSteps,
    String? stepNote,
    bool clearStepNote = false,
    bool? dashboardLoading,
    String? loadError,
    bool clearLoadError = false,
  }) {
    return FitState(
      ready: ready ?? this.ready,
      busy: busy ?? this.busy,
      user: clearUser ? null : user ?? this.user,
      dashboard: dashboard ?? this.dashboard,
      locale: locale ?? this.locale,
      dark: dark ?? this.dark,
      baseUrl: baseUrl ?? this.baseUrl,
      notice: clearNotice ? null : notice ?? this.notice,
      pending: pending ?? this.pending,
      liveSteps: liveSteps ?? this.liveSteps,
      stepNote: clearStepNote ? null : stepNote ?? this.stepNote,
      dashboardLoading: dashboardLoading ?? this.dashboardLoading,
      loadError: clearLoadError ? null : loadError ?? this.loadError,
    );
  }
}

const kApiBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: 'https://fftdesi-81xd.vercel.app',
);

final fitProvider = NotifierProvider<FitController, FitState>(FitController.new);

class FitController extends Notifier<FitState> {
  late FitApi api;
  final local = LocalStore();
  final storage = const FlutterSecureStorage();
  StreamSubscription<StepCount>? _stepsSub;
  DateTime? _lastStepSync;
  int _lastSyncedSteps = -1;
  bool _stepStarting = false;

  @override
  FitState build() {
    api = FitApi(kApiBase, storage);
    Future.microtask(restore);
    return const FitState();
  }

  Future<void> restore() async {
    try {
    final prefs = await SharedPreferences.getInstance();
    final url = prefs.getString('baseUrl') ?? kApiBase;
    api.baseUrl = url;
    api.configure();
    Map<String, dynamic>? user;
    final access = await storage.read(key: 'access');
    if (access != null) {
      try {
        user = Map<String, dynamic>.from(await api.get('/users/me') as Map);
      } catch (_) {
        user = null;
      }
    }
    final queued = await local.pending();
    state = state.copy(
      ready: true,
      user: user,
      clearUser: user == null,
      locale: prefs.getString('locale') ?? 'en',
      dark: prefs.getBool('dark') ?? false,
      baseUrl: url,
      pending: queued.length,
    );
    if (user != null) {
      await refreshDashboard();
      await syncOutbox();
      await startStepCounter();
    }
    } catch (_) {
      state = state.copy(ready: true);
    }
  }

  Future<void> setBaseUrl(String url) async {
    final clean = url.trim().replaceAll(RegExp(r'/+$'), '');
    api.baseUrl = clean;
    api.configure();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('baseUrl', clean);
    state = state.copy(baseUrl: clean);
  }

  Future<void> setLocale(String locale) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('locale', locale);
    state = state.copy(locale: locale);
    if (state.signedIn) await api.put('/users/me/preferences', data: {'language': locale});
  }

  Future<void> setDark(bool dark) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('dark', dark);
    state = state.copy(dark: dark);
    if (state.signedIn) await api.put('/users/me/preferences', data: {'theme': dark ? 'dark' : 'light'});
  }

  Future<String?> login(String email, String password) => _auth('/auth/login', {'email': email, 'password': password});
  Future<String?> register(String name, String email, String password) => _auth('/auth/register', {'full_name': name, 'email': email, 'password': password});

  Future<String?> _auth(String path, Map<String, dynamic> body) async {
    state = state.copy(busy: true, clearNotice: true);
    try {
      final data = Map<String, dynamic>.from(await api.post(path, data: body) as Map);
      await api.saveTokens(data);
      final user = Map<String, dynamic>.from(await api.get('/users/me') as Map);
      state = state.copy(busy: false, user: user);
      await refreshDashboard();
      await startStepCounter();
      return null;
    } catch (error) {
      state = state.copy(busy: false);
      return error.toString();
    }
  }

  Future<String?> forgot(String email) async {
    try {
      final data = await api.post('/auth/forgot-password', data: {'email': email});
      final token = data is Map ? data['reset_token'] : null;
      return token == null ? 'If an account exists, a reset was issued.' : 'Development reset token: $token';
    } catch (error) {
      return error.toString();
    }
  }

  Future<String?> resetPassword(String token, String password) async {
    try {
      await api.post('/auth/reset-password', data: {'token': token, 'password': password});
      return null;
    } catch (error) {
      return error.toString();
    }
  }

  Future<void> logout() async {
    try {
      final refresh = await storage.read(key: 'refresh');
      if (refresh != null) await api.post('/auth/logout', data: {'refresh_token': refresh});
    } catch (_) {}
    await api.clear();
    state = state.copy(clearUser: true, dashboard: {});
  }

  Future<String?> onboard(Map<String, dynamic> body) async {
    try {
      final user = Map<String, dynamic>.from(await api.put('/users/me/onboarding', data: body) as Map);
      state = state.copy(user: user);
      await refreshDashboard();
      return null;
    } catch (error) {
      return error.toString();
    }
  }

  Future<void> refreshDashboard() async {
    state = state.copy(dashboardLoading: true, clearLoadError: true);
    try {
      final data = Map<String, dynamic>.from(await api.get('/dashboard/today') as Map);
      await local.saveRecord('dashboard', data);
      state = state.copy(dashboard: data, dashboardLoading: false);
    } catch (_) {
      final cached = await local.readRecord('dashboard');
      state = state.copy(
        dashboard: cached is Map ? Map<String, dynamic>.from(cached) : state.dashboard,
        dashboardLoading: false,
        loadError: 'Today\'s numbers could not be loaded. Pull down to try again.',
      );
    }
  }

  Future<List<Map<String, dynamic>>> suggestFoods(String query) async {
    final term = query.trim();
    if (term.length < 2) return [];
    try {
      final data = await api.get('/foods/suggest', query: {'q': term, 'limit': 8});
      final items = ((data as Map)['items'] as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
      await local.cacheFoods(items);
      state = state.copy(clearNotice: true);
      return items;
    } catch (_) {
      state = state.copy(notice: 'Food search could not reach the server.');
      return local.searchFoods(term);
    }
  }

  Future<Map<String, dynamic>?> mealIdea() async {
    final data = await api.post('/ai/meal-idea');
    return Map<String, dynamic>.from(data as Map);
  }

  Future<String> dailyTip() async {
    final data = await api.get('/ai/tip');
    return (data as Map)['tip']?.toString() ?? '';
  }

  Future<List<Map<String, dynamic>>> searchFoods(String query, {String? cuisine}) async {
    try {
      final data = await api.get('/foods/search', query: {'q': query, 'cuisine': cuisine, 'page_size': 20});
      final items = ((data as Map)['items'] as List).map((item) => Map<String, dynamic>.from(item as Map)).toList();
      await local.cacheFoods(items);
      return items;
    } catch (_) {
      state = state.copy(notice: 'Food search could not reach the server.');
      return local.searchFoods(query);
    }
  }

  Future<String?> logFood(Map<String, dynamic> body) async {
    body['client_mutation_id'] ??= _mutation();
    try {
      await api.post('/food-diary', data: body);
      await refreshDashboard();
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('diary', body);
      state = state.copy(pending: state.pending + 1, notice: 'offline');
      return 'offline';
    }
  }

  Future<Map<String, dynamic>> diary([String? day]) async {
    try {
      final query = <String, dynamic>{};
      if (day != null) query['date_value'] = day;
      final data = Map<String, dynamic>.from(await api.get('/food-diary', query: query) as Map);
      await local.saveRecord('diary-${data['date']}', data);
      return data;
    } catch (_) {
      final cached = await local.readRecord('diary-${day ?? DateTime.now().toIso8601String().substring(0, 10)}');
      if (cached is Map) return Map<String, dynamic>.from(cached);
      return {'items': [], 'summary': {'logged': false}};
    }
  }

  Future<void> deleteDiary(int id) async {
    await api.delete('/food-diary/$id');
    await refreshDashboard();
  }

  Future<void> copyYesterday() async {
    final today = DateTime.now();
    final yesterday = today.subtract(const Duration(days: 1));
    String stamp(DateTime value) => value.toIso8601String().substring(0, 10);
    await api.post('/food-diary/copy-day', data: {'from_date': stamp(yesterday), 'to_date': stamp(today)});
    await refreshDashboard();
  }

  Future<Map<String, dynamic>> calculateRecipe(List<Map<String, dynamic>> ingredients, double waterLoss, double servings) async {
    final data = await api.post('/recipes/calculate', data: {'ingredients': ingredients, 'water_loss_g': waterLoss, 'servings': servings});
    return Map<String, dynamic>.from(data as Map);
  }

  Future<Map<String, dynamic>> generatePlan(Map<String, dynamic> body) async {
    final data = Map<String, dynamic>.from(await api.post('/plans/generate', data: body) as Map);
    await local.saveRecord('plan', data);
    await refreshDashboard();
    return data;
  }

  Future<Map<String, dynamic>?> currentPlan() async {
    try {
      final data = await api.get('/plans/current');
      if (data == null) return null;
      final plan = Map<String, dynamic>.from(data as Map);
      await local.saveRecord('plan', plan);
      return plan;
    } catch (_) {
      final cached = await local.readRecord('plan');
      return cached is Map ? Map<String, dynamic>.from(cached) : null;
    }
  }

  Future<int?> readHealthSteps() async {
    try {
      final health = Health();
      await health.configure();
      const types = [HealthDataType.STEPS];
      final granted = await health.requestAuthorization(types);
      if (!granted) return null;
      final now = DateTime.now();
      final start = DateTime(now.year, now.month, now.day);
      return await health.getTotalStepsInInterval(start, now);
    } catch (_) {
      return null;
    }
  }

  Future<void> startStepCounter() async {
    if (_stepsSub != null || _stepStarting) return;
    _stepStarting = true;
    final status = await Permission.activityRecognition.request();
    if (!status.isGranted) {
      _stepStarting = false;
      state = state.copy(stepNote: 'Allow physical activity so steps can be counted while you walk.');
      return;
    }
    final prefs = await SharedPreferences.getInstance();
    final today = DateTime.now().toIso8601String().substring(0, 10);
    if (prefs.getString('step_day') == today) {
      state = state.copy(liveSteps: prefs.getInt('step_today') ?? 0, clearStepNote: true);
    }
    _stepsSub = Pedometer.stepCountStream.listen((event) async {
      final stored = await SharedPreferences.getInstance();
      final day = DateTime.now().toIso8601String().substring(0, 10);
      var base = stored.getInt('step_base');
      final savedDay = stored.getString('step_day');
      if (savedDay != day || base == null || event.steps < base) {
        base = event.steps;
        await stored.setInt('step_base', base);
        await stored.setString('step_day', day);
      }
      final count = max(0, event.steps - base);
      await stored.setInt('step_today', count);
      state = state.copy(liveSteps: count, clearStepNote: true);
      final now = DateTime.now();
      final due = _lastStepSync == null || now.difference(_lastStepSync!) > const Duration(seconds: 20);
      if (state.signedIn && count != _lastSyncedSteps && due) {
        _lastStepSync = now;
        _lastSyncedSteps = count;
        await saveSteps(count, 'sensor', quiet: true);
      }
    }, onError: (_) {
      state = state.copy(stepNote: 'The step sensor is unavailable. Enter steps manually.');
    });
  }

  Future<String?> saveSteps(int steps, String source, {bool quiet = false}) async {
    final body = {'day': DateTime.now().toIso8601String().substring(0, 10), 'steps': steps, 'source': source};
    try {
      await api.post('/activity/steps/sync', data: body);
      if (quiet) {
        final dash = Map<String, dynamic>.from(state.dashboard ?? {});
        dash['steps'] = {'steps': steps, 'source': source, 'distance_m': (steps * 0.75).round()};
        state = state.copy(dashboard: dash, liveSteps: steps);
      } else {
        await refreshDashboard();
      }
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('steps', body);
      return 'offline';
    }
  }

  Future<String?> saveWorkout(Map<String, dynamic> body) async {
    body['client_mutation_id'] ??= _mutation();
    body['started_at'] ??= DateTime.now().toUtc().toIso8601String();
    try {
      await api.post('/activity/workouts', data: body);
      await refreshDashboard();
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('workout', body);
      return 'offline';
    }
  }

  Future<List<dynamic>> workouts() async {
    try {
      final data = await api.get('/activity/workouts');
      return data as List;
    } catch (_) {
      return [];
    }
  }

  Future<String?> saveWeight(double kg) async {
    final body = {'weight_kg': kg, 'client_mutation_id': _mutation()};
    try {
      await api.post('/weight', data: body);
      await refreshDashboard();
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('weight', body);
      return 'offline';
    }
  }

  Future<Map<String, dynamic>> weightHistory() async {
    final data = await api.get('/weight/history');
    return Map<String, dynamic>.from(data as Map);
  }

  Future<String?> saveWater(int ml) async {
    final body = {'amount_ml': ml, 'client_mutation_id': _mutation()};
    try {
      await api.post('/water', data: body);
      await refreshDashboard();
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('water', body);
      return 'offline';
    }
  }

  Future<String?> saveSleep(DateTime start, DateTime end) async {
    final body = {'sleep_start': start.toUtc().toIso8601String(), 'sleep_end': end.toUtc().toIso8601String(), 'source': 'manual', 'client_mutation_id': _mutation()};
    try {
      await api.post('/sleep', data: body);
      return null;
    } on ApiException catch (error) {
      if (!error.offline) return error.message;
      await local.enqueue('sleep', body);
      return 'offline';
    }
  }

  Future<List<dynamic>> sleepHistory() async => await api.get('/sleep/history') as List;

  Future<String> chat(String message, {int? sessionId}) async {
    final body = <String, dynamic>{'message': message, 'language': state.locale};
    if (sessionId != null) body['session_id'] = sessionId;
    final data = await api.post('/ai/consultant/chat', data: body);
    return (data as Map)['reply'].toString();
  }

  Future<Map<String, dynamic>> scan(String path) async {
    final data = await api.upload('/ai/food-recognition', path);
    return Map<String, dynamic>.from(data as Map);
  }

  Future<void> deleteScan(int id) => api.delete('/ai/scans/$id');

  Future<List<dynamic>> consultants() async => await api.get('/consultants') as List;
  Future<List<dynamic>> bookings() async => await api.get('/consultant-bookings') as List;

  Future<String?> book(int consultantId, int serviceId, DateTime start) async {
    try {
      await api.post('/consultant-bookings', data: {'consultant_id': consultantId, 'service_id': serviceId, 'start_at': start.toUtc().toIso8601String()});
      return null;
    } catch (error) {
      return error.toString();
    }
  }

  Future<Map<String, dynamic>> weeklyReport() async => Map<String, dynamic>.from(await api.get('/reports/weekly') as Map);

  Future<String> exportCsv() async {
    final response = await api.dio.get('/reports/export', queryParameters: {'fmt': 'csv'});
    return response.data.toString();
  }

  Future<List<dynamic>> grocery() async => await api.get('/grocery-lists') as List;

  Future<void> createGrocery(int? mealPlanId) async {
    final body = <String, dynamic>{'name': 'Weekly shop'};
    if (mealPlanId != null) body['meal_plan_id'] = mealPlanId;
    await api.post('/grocery-lists', data: body);
  }

  Future<void> updateGrocery(int id, Map<String, dynamic> body) => api.put('/grocery-lists/$id', data: body);

  Future<void> syncOutbox() async {
    final rows = await local.pending();
    for (final row in rows) {
      final kind = row['kind'] as String;
      final payload = Map<String, dynamic>.from(row['payload'] as Map);
      try {
        switch (kind) {
          case 'diary':
            await api.post('/food-diary', data: payload);
          case 'water':
            await api.post('/water', data: payload);
          case 'weight':
            await api.post('/weight', data: payload);
          case 'workout':
            await api.post('/activity/workouts', data: payload);
          case 'steps':
            await api.post('/activity/steps/sync', data: payload);
          case 'sleep':
            await api.post('/sleep', data: payload);
        }
        await local.remove(row['id'] as int);
      } on ApiException catch (error) {
        if (error.offline) break;
        await local.remove(row['id'] as int);
      }
    }
    final left = await local.pending();
    state = state.copy(pending: left.length);
    await refreshDashboard();
  }

  Future<void> deleteAccount() async {
    await api.delete('/users/me');
    await api.clear();
    state = state.copy(clearUser: true);
  }

  String _mutation() => '${DateTime.now().microsecondsSinceEpoch}-${Random().nextInt(99999)}';
}
