import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.offline = false});
  final String message;
  final bool offline;
  @override
  String toString() => message;
}

class FitApi {
  FitApi(this.baseUrl, this.storage);
  String baseUrl;
  final FlutterSecureStorage storage;
  late final Dio dio = Dio(BaseOptions(
    baseUrl: '$baseUrl/api/v1',
    connectTimeout: const Duration(seconds: 8),
    receiveTimeout: const Duration(seconds: 20),
  ));
  bool _ready = false;

  void configure() {
    if (_ready) {
      dio.options.baseUrl = '$baseUrl/api/v1';
      return;
    }
    dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await storage.read(key: 'access');
        if (token != null) options.headers['Authorization'] = 'Bearer $token';
        handler.next(options);
      },
      onError: (error, handler) async {
        final status = error.response?.statusCode;
        final already = error.requestOptions.extra['retried'] == true;
        if (status == 401 && !already && !error.requestOptions.path.contains('/auth/')) {
          final refresh = await storage.read(key: 'refresh');
          if (refresh != null) {
            try {
              final response = await Dio().post('$baseUrl/api/v1/auth/refresh', data: {'refresh_token': refresh});
              final data = response.data['data'] as Map;
              await storage.write(key: 'access', value: data['access_token'] as String);
              await storage.write(key: 'refresh', value: data['refresh_token'] as String);
              final request = error.requestOptions;
              request.extra['retried'] = true;
              request.headers['Authorization'] = 'Bearer ${data['access_token']}';
              handler.resolve(await dio.fetch(request));
              return;
            } catch (_) {
              await storage.delete(key: 'access');
              await storage.delete(key: 'refresh');
            }
          }
        }
        handler.next(error);
      },
    ));
    _ready = true;
  }

  Future<dynamic> get(String path, {Map<String, dynamic>? query}) async => _send(() => dio.get(path, queryParameters: query));
  Future<dynamic> post(String path, {Object? data, Map<String, dynamic>? query}) async => _send(() => dio.post(path, data: data, queryParameters: query));
  Future<dynamic> put(String path, {Object? data}) async => _send(() => dio.put(path, data: data));
  Future<dynamic> delete(String path) async => _send(() => dio.delete(path));

  Future<dynamic> upload(String path, String filePath) async {
    final form = FormData.fromMap({'file': await MultipartFile.fromFile(filePath, filename: 'meal.jpg')});
    return _send(() => dio.post(path, data: form));
  }

  Future<dynamic> _send(Future<Response<dynamic>> Function() call) async {
    try {
      final response = await call();
      final body = response.data;
      if (body is Map && body.containsKey('data')) return body['data'];
      return body;
    } on DioException catch (error) {
      final offline = error.type == DioExceptionType.connectionError || error.type == DioExceptionType.connectionTimeout;
      final data = error.response?.data;
      String message = offline ? 'offline' : 'The request could not be completed.';
      if (data is Map && data['error'] is Map) {
        message = (data['error']['message'] ?? message).toString();
      }
      throw ApiException(message, offline: offline);
    }
  }

  Future<void> saveTokens(Map data) async {
    await storage.write(key: 'access', value: data['access_token'] as String);
    await storage.write(key: 'refresh', value: data['refresh_token'] as String);
  }

  Future<void> clear() async {
    await storage.delete(key: 'access');
    await storage.delete(key: 'refresh');
  }
}
