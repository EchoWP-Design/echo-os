// Einstellungen der App. Zugangscode und API-Schlüssel liegen verschlüsselt im
// Android-Schlüsselspeicher (flutter_secure_storage), nie im Klartext.
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

class EchoSettings {
  EchoSettings({this.piHost = '', this.piToken = '', this.claudeKey = '', this.viewMode = 'auto'});

  String piHost;
  String piToken;
  String claudeKey;

  /// 'auto' (Fernseher erkennen), 'tv' (Kachel-Startseite) oder 'phone' (Fernbedienung für den Pi).
  String viewMode;

  bool get hasPi => piHost.trim().isNotEmpty && piToken.trim().isNotEmpty;
  bool get hasClaude => claudeKey.trim().isNotEmpty;

  static const _secure = FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
  );

  static Future<EchoSettings> load() async {
    final prefs = await SharedPreferences.getInstance();
    return EchoSettings(
      piHost: prefs.getString('pi_host') ?? '',
      piToken: await _secure.read(key: 'pi_token') ?? '',
      claudeKey: await _secure.read(key: 'claude_key') ?? '',
      viewMode: prefs.getString('view_mode') ?? 'auto',
    );
  }

  Future<void> save() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('pi_host', piHost.trim());
    await prefs.setString('view_mode', viewMode);
    await _write('pi_token', piToken.trim());
    await _write('claude_key', claudeKey.trim());
  }

  static Future<void> _write(String key, String value) async {
    if (value.isEmpty) {
      await _secure.delete(key: key);
    } else {
      await _secure.write(key: key, value: value);
    }
  }
}
