// Verbindung zum ECHO-Agenten auf dem Echo-OS-Pi (Port 8090, Zugangscode als Bearer-Token).
// Dieselbe Schnittstelle nutzt auch die Web-Oberfläche des Agenten.
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'chat.dart' show piBase;

class PiAuthException implements Exception {
  @override
  String toString() => 'Zugangscode falsch';
}

class PiApi {
  PiApi(this.host, this.token, {http.Client? client}) : client = client ?? http.Client();

  final String host;
  final String token;
  final http.Client client;

  Map<String, String> get _headers => {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      };

  Uri _url(String path) => piBase(host).replace(path: path);

  Map<String, dynamic> _decode(http.Response r) {
    if (r.statusCode == 401) throw PiAuthException();
    final data = jsonDecode(utf8.decode(r.bodyBytes));
    return data is Map<String, dynamic> ? data : {'ergebnis': data};
  }

  /// Systemzustand, laufende Wiedergabe, Updates, Sicherheit, Laufwerke.
  Future<Map<String, dynamic>> status() async =>
      _decode(await client.get(_url('/api/status'), headers: _headers).timeout(const Duration(seconds: 10)));

  /// Aktion wie im Agenten: back_to_kodi, check_updates, apply_updates, security, scan,
  /// reboot, launch (service), control (command, value).
  Future<Map<String, dynamic>> action(String action, [Map<String, Object?> extra = const {}]) async =>
      _decode(await client
          .post(_url('/api/action'), headers: _headers, body: jsonEncode({'action': action, ...extra}))
          .timeout(const Duration(minutes: 30)));

  /// Streaming-Dienste des Pi (ohne Anmeldung abrufbar).
  Future<List<Map<String, dynamic>>> services() async {
    final r = await client.get(_url('/api/services')).timeout(const Duration(seconds: 10));
    final data = jsonDecode(utf8.decode(r.bodyBytes));
    return data is List ? data.whereType<Map<String, dynamic>>().toList() : <Map<String, dynamic>>[];
  }
}

/// Antwort einer Aktion als kurzer Satz (wie in der Web-Oberfläche des Agenten).
String describeResult(Map<String, dynamic> r) {
  if (r['fehler'] != null) return '⚠ ${r['fehler']}';
  if (r['dienst'] != null) return '▶ ${r['dienst']} wird auf dem Fernseher gestartet.';
  final warnungen = r['warnungen'];
  if (warnungen is List) {
    if (warnungen.isEmpty) {
      return '✔ Sicherheit: alles in Ordnung (Firewall aktiv, ${r['gesperrte_ips'] ?? 0} gesperrte IPs).';
    }
    return '⚠ ${warnungen.join('\n⚠ ')}';
  }
  final anzahl = r['anzahl'];
  if (anzahl is num) {
    if (anzahl == 0) return '✔ System ist aktuell.';
    final sec = r['sicherheit'];
    final secText = sec is List && sec.isNotEmpty ? ', davon Sicherheit: ${sec.join(', ')}' : '';
    return '$anzahl Updates verfügbar$secText.';
  }
  if (r['info'] != null) return '✔ ${r['info']}';
  if (r['ok'] == true) return '✔ Erledigt.';
  if (r['ok'] == false) return '⚠ Hat nicht geklappt.';
  return 'Erledigt.';
}

/// „Serie – Folge“ oder Filmtitel aus dem Status, sonst „Nichts“.
String nowPlayingText(Map<String, dynamic> status) {
  final np = status['now_playing'];
  if (np is Map && np['spielt'] is Map) {
    final p = np['spielt'] as Map;
    final title = (p['title'] ?? p['label'] ?? '').toString();
    final show = (p['showtitle'] ?? '').toString();
    if (show.isNotEmpty) return '$show – $title';
    if (title.isNotEmpty) return title;
  }
  final sys = status['system'];
  if (sys is Map && sys['streaming_app_aktiv'] == true) return 'Streaming-App';
  return 'Nichts';
}
