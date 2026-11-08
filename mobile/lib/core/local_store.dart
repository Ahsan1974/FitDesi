import 'dart:convert';

import 'package:path/path.dart' as p;
import 'package:sqflite/sqflite.dart';

class LocalStore {
  Database? _db;

  Future<Database> get db async {
    if (_db != null) return _db!;
    final file = p.join(await getDatabasesPath(), 'fitdesi.db');
    _db = await openDatabase(file, version: 1, onCreate: (database, version) async {
      await database.execute('CREATE TABLE outbox (id INTEGER PRIMARY KEY, kind TEXT, payload TEXT, created_at TEXT)');
      await database.execute('CREATE TABLE food_cache (id INTEGER PRIMARY KEY, name TEXT, payload TEXT)');
      await database.execute('CREATE TABLE records (key TEXT PRIMARY KEY, payload TEXT)');
    });
    return _db!;
  }

  Future<void> enqueue(String kind, Map<String, dynamic> payload) async {
    final database = await db;
    await database.insert('outbox', {
      'kind': kind,
      'payload': jsonEncode(payload),
      'created_at': DateTime.now().toUtc().toIso8601String(),
    });
  }

  Future<List<Map<String, dynamic>>> pending() async {
    final database = await db;
    final rows = await database.query('outbox', orderBy: 'id');
    return rows.map((row) => {
      'id': row['id'],
      'kind': row['kind'],
      'payload': jsonDecode(row['payload'] as String),
    }).toList();
  }

  Future<void> remove(int id) async {
    final database = await db;
    await database.delete('outbox', where: 'id = ?', whereArgs: [id]);
  }

  Future<void> cacheFoods(List foods) async {
    final database = await db;
    final batch = database.batch();
    for (final food in foods) {
      if (food is! Map) continue;
      batch.insert(
        'food_cache',
        {'id': food['id'], 'name': '${food['name_en']} ${food['name_ur'] ?? ''} ${food['name_roman'] ?? ''}'.toLowerCase(), 'payload': jsonEncode(food)},
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
    await batch.commit(noResult: true);
  }

  Future<List<Map<String, dynamic>>> searchFoods(String query) async {
    final database = await db;
    final rows = await database.query('food_cache', where: 'name LIKE ?', whereArgs: ['%${query.toLowerCase()}%'], limit: 30);
    return rows.map((row) => Map<String, dynamic>.from(jsonDecode(row['payload'] as String) as Map)).toList();
  }

  Future<void> saveRecord(String key, Object value) async {
    final database = await db;
    await database.insert('records', {'key': key, 'payload': jsonEncode(value)}, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<dynamic> readRecord(String key) async {
    final database = await db;
    final rows = await database.query('records', where: 'key = ?', whereArgs: [key], limit: 1);
    if (rows.isEmpty) return null;
    return jsonDecode(rows.first['payload'] as String);
  }
}
