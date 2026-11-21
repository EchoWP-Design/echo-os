// ECHO-Chat: bevorzugt der Agent auf dem Echo-OS-Pi (steuert Kodi, kennt die
// Bibliothek), sonst direkt Claude mit eigenem API-Schlüssel.
import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'settings.dart';

abstract class ChatBackend {
  /// Kurzer Name für die Anzeige, z. B. "Echo-OS-Pi".
  String get label;
  Future<String> send(String text);
}

/// Baut aus "192.168.178.193", "echo-os:8090" oder "http://…" die Basisadresse.
Uri piBase(String host) {
  var h = host.trim();
  if (h.endsWith('/')) h = h.substring(0, h.length - 1);
  if (h.contains('://')) return Uri.parse(h);
  if (h.contains(':')) return Uri.parse('http://$h');
  return Uri.parse('http://$h:8090');
}

class PiBackend implements ChatBackend {
  PiBackend(this.host, this.token, {http.Client? client}) : client = client ?? http.Client();

  final String host;
  final String token;
  final http.Client client;

  @override
  String get label => 'Echo-OS-Pi';

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  Uri _url(String path) => piBase(host).replace(path: path);

  Future<bool> reachable() async {
    try {
      final r = await client
          .get(_url('/api/status'), headers: _headers)
          .timeout(const Duration(seconds: 4));
      return r.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  @override
  Future<String> send(String text) async {
    final r = await client
        .post(_url('/api/chat'), headers: _headers, body: jsonEncode({'message': text}))
        .timeout(const Duration(seconds: 120));
    if (r.statusCode == 401) return 'Der Zugangscode stimmt nicht – bitte in den Einstellungen prüfen.';
    final data = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    return (data['reply'] ?? data['fehler'] ?? 'Keine Antwort').toString();
  }
}

class ClaudeBackend implements ChatBackend {
  ClaudeBackend(this.apiKey, {http.Client? client, this.model = 'claude-haiku-5-5'})
      : client = client ?? http.Client();

  final String apiKey;
  final String model;
  final http.Client client;
  final List<Map<String, String>> _history = [];

  static final url = Uri.parse('https://api.anthropic.com/v1/messages');
  static const system =
      'Du bist ECHO, der Assistent von Echo-OS, einem Media-Center. Du läufst gerade in der '
      'Echo-App auf einem Fernseher ohne Verbindung zum Echo-OS-Pi, kannst also nichts steuern. '
      'Hilf bei Fragen zu Filmen, Serien, Streamingdiensten und Technik. Antworte kurz, '
      'freundlich und auf Deutsch.';

  @override
  String get label => 'Claude';

  @override
  Future<String> send(String text) async {
    _history.add({'role': 'user', 'content': text});
    while (_history.length > 20) {
      _history.removeAt(0);
    }
    if (_history.first['role'] != 'user') _history.removeAt(0);
    final r = await client
        .post(url,
            headers: {
              'x-api-key': apiKey,
              'anthropic-version': '2023-06-01',
              'content-type': 'application/json',
            },
            body: jsonEncode({
              'model': model,
              'max_tokens': 1024,
              'system': system,
              'messages': _history,
            }))
        .timeout(const Duration(seconds: 90));
    final data = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    if (r.statusCode != 200) {
      _history.removeLast();
      final err = (data['error'] as Map<String, dynamic>?)?['message'] ?? 'Fehler ${r.statusCode}';
      if (r.statusCode == 401) return 'Der Claude-API-Schlüssel wurde abgelehnt – bitte in den Einstellungen prüfen.';
      return 'Claude ist gerade nicht erreichbar ($err).';
    }
    final reply = ((data['content'] as List<dynamic>?) ?? const [])
        .whereType<Map<String, dynamic>>()
        .where((b) => b['type'] == 'text')
        .map((b) => b['text'].toString())
        .join()
        .trim();
    _history.add({'role': 'assistant', 'content': reply.isEmpty ? '…' : reply});
    return reply.isEmpty ? 'Keine Antwort erhalten.' : reply;
  }
}

/// Wählt den Chat: Pi, wenn eingerichtet und erreichbar, sonst Claude, sonst nichts.
Future<ChatBackend?> pickBackend(EchoSettings s, {http.Client? client}) async {
  if (s.hasPi) {
    final pi = PiBackend(s.piHost, s.piToken, client: client);
    if (await pi.reachable()) return pi;
  }
  if (s.hasClaude) return ClaudeBackend(s.claudeKey, client: client);
  return null;
}
