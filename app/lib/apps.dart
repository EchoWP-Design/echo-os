// Verbindung zur Android-Seite (MainActivity.kt): installierte Apps lesen,
// Apps starten, App-Store öffnen, Fernseher erkennen.
import 'package:flutter/services.dart';

class AppsApi {
  const AppsApi([this.channel = const MethodChannel('echoos/apps')]);

  final MethodChannel channel;

  /// Paketname → angezeigter Name aller startbaren Apps.
  Future<Map<String, String>> installed() async {
    try {
      final raw = await channel.invokeMethod<Map<Object?, Object?>>('installed');
      return {
        for (final e in (raw ?? const {}).entries) e.key.toString(): e.value.toString(),
      };
    } on PlatformException {
      return {};
    } on MissingPluginException {
      return {};
    }
  }

  Future<bool> launch(String package) => _bool('launch', {'package': package});

  Future<bool> openStore(String package) => _bool('store', {'package': package});

  Future<bool> isTv() => _bool('isTv');

  Future<bool> _bool(String method, [Map<String, Object?>? args]) async {
    try {
      return (await channel.invokeMethod<bool>(method, args)) ?? false;
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }
}
