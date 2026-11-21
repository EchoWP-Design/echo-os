// Streaming-Dienste aus der Echo-OS-Liste (services.json) und die Auswahl der
// passenden Android-App. Dieselbe Logik wie im Kodi-Addon (echostream.py).
import 'dart:convert';

import 'package:flutter/services.dart' show rootBundle;

class StreamingService {
  const StreamingService({
    required this.id,
    required this.name,
    required this.color,
    this.tv = const [],
    this.mobile = const [],
    this.labels = const [],
  });

  final String id;
  final String name;
  final String color;
  final List<String> tv;
  final List<String> mobile;
  final List<String> labels;

  factory StreamingService.fromJson(Map<String, dynamic> json) {
    final android = (json['android'] as Map<String, dynamic>?) ?? const {};
    List<String> list(Object? v) => v is List ? v.map((e) => e.toString()).toList() : const [];
    return StreamingService(
      id: json['id'] as String,
      name: json['name'] as String,
      color: (json['color'] as String?) ?? '#333333',
      tv: list(android['tv']),
      mobile: list(android['mobile']),
      labels: list(json['labels']),
    );
  }
}

List<StreamingService> parseServices(String jsonText) {
  final data = jsonDecode(jsonText) as List<dynamic>;
  return data
      .map((e) => StreamingService.fromJson(e as Map<String, dynamic>))
      .where((s) => s.tv.isNotEmpty || s.mobile.isNotEmpty)
      .toList();
}

Future<List<StreamingService>> loadServices() async =>
    parseServices(await rootBundle.loadString('assets/services.json'));

/// Vergleichbare Schreibweise: klein, "+" wird "plus", nur Buchstaben und Ziffern.
String normalizeName(String text) =>
    text.toLowerCase().replaceAll('+', 'plus').replaceAll(RegExp(r'[^a-z0-9]'), '');

/// Paketnamen in sinnvoller Reihenfolge: auf dem Fernseher zuerst die TV-Apps.
List<String> candidates(StreamingService s, {required bool tv}) {
  final ordered = tv ? [...s.tv, ...s.mobile] : [...s.mobile, ...s.tv];
  final seen = <String>{};
  return [for (final p in ordered) if (seen.add(p)) p];
}

/// Findet die installierte App eines Dienstes (Paketname oder angezeigter Name).
String? findPackage(StreamingService s, Map<String, String> installed, {required bool tv}) {
  for (final p in candidates(s, tv: tv)) {
    if (installed.containsKey(p)) return p;
  }
  final names = {normalizeName(s.name), ...s.labels.map(normalizeName)};
  for (final entry in installed.entries) {
    if (names.contains(normalizeName(entry.value))) return entry.key;
  }
  return null;
}

/// Paket, das im App-Store geöffnet wird, wenn der Dienst fehlt.
String? storePackage(StreamingService s, {required bool tv}) {
  final preferred = tv ? s.tv : s.mobile;
  if (preferred.isNotEmpty) return preferred.first;
  final all = candidates(s, tv: tv);
  return all.isEmpty ? null : all.first;
}

const kodiPackage = 'org.xbmc.kodi';

/// "#rrggbb" in einen Farbwert für Flutter.
int colorValue(String hex) {
  final h = hex.replaceAll('#', '');
  return int.tryParse('ff$h', radix: 16) ?? 0xff333333;
}
