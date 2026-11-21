// Einstellungen: Echo-OS-Pi (Adresse + Zugangscode) und optional ein eigener
// Claude-API-Schlüssel. Beides bleibt verschlüsselt auf diesem Gerät.
import 'package:flutter/material.dart';

import '../chat.dart';
import '../settings.dart';
import '../widgets/neon.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.settings, this.onSave});

  final EchoSettings settings;

  /// Zum Testen austauschbar; Standard speichert dauerhaft.
  final Future<void> Function(EchoSettings settings)? onSave;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final _host = TextEditingController(text: widget.settings.piHost);
  late final _token = TextEditingController(text: widget.settings.piToken);
  late final _key = TextEditingController(text: widget.settings.claudeKey);
  String _status = '';

  @override
  void dispose() {
    _host.dispose();
    _token.dispose();
    _key.dispose();
    super.dispose();
  }

  void _apply() {
    widget.settings
      ..piHost = _host.text.trim()
      ..piToken = _token.text.trim()
      ..claudeKey = _key.text.trim();
  }

  Future<void> _save() async {
    _apply();
    final onSave = widget.onSave;
    if (onSave != null) {
      await onSave(widget.settings);
    } else {
      await widget.settings.save();
    }
    if (mounted) setState(() => _status = 'Gespeichert.');
  }

  Future<void> _test() async {
    _apply();
    setState(() => _status = 'Teste Verbindung …');
    String result;
    if (!widget.settings.hasPi) {
      result = 'Pi: Adresse und Zugangscode fehlen.';
    } else {
      final ok = await PiBackend(widget.settings.piHost, widget.settings.piToken).reachable();
      result = ok
          ? 'Pi erreichbar – ECHO antwortet über deinen Echo-OS-Pi.'
          : 'Pi nicht erreichbar oder Code falsch (${piBase(widget.settings.piHost)}).';
    }
    if (mounted) setState(() => _status = result);
  }

  Widget _field(String label, TextEditingController c, {String? hint, bool secret = false, Key? key}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextField(
        key: key,
        controller: c,
        obscureText: secret,
        autocorrect: false,
        enableSuggestions: !secret,
        decoration: InputDecoration(labelText: label, hintText: hint),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(backgroundColor: neonBg, title: const Text('Einstellungen')),
      body: ListView(padding: const EdgeInsets.all(24), children: [
        const Text('ECHO auf deinem Echo-OS-Pi',
            style: TextStyle(color: neonCyan, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        const Text(
          'Adresse und Zugangscode zeigt der Pi beim Start unten rechts auf dem Fernseher '
          '(oder im Agenten über „Code auf dem Fernseher anzeigen“).',
          style: TextStyle(color: neonDim),
        ),
        const SizedBox(height: 14),
        _field('Pi-Adresse', _host, hint: 'z. B. 192.168.178.193', key: const ValueKey('pi-host')),
        _field('Zugangscode', _token, secret: true, key: const ValueKey('pi-token')),
        const SizedBox(height: 10),
        const Text('Ohne Pi: direkt mit Claude',
            style: TextStyle(color: neonCyan, fontSize: 18, fontWeight: FontWeight.bold)),
        const SizedBox(height: 6),
        const Text(
          'Optional. Eigener API-Schlüssel aus der Claude Console; wird nur genutzt, wenn der Pi '
          'nicht erreichbar ist, und kostet pro Nachricht.',
          style: TextStyle(color: neonDim),
        ),
        const SizedBox(height: 14),
        _field('Claude-API-Schlüssel', _key, hint: 'sk-ant-…', secret: true, key: const ValueKey('claude-key')),
        const Text('Code und Schlüssel werden verschlüsselt nur auf diesem Gerät gespeichert.',
            style: TextStyle(color: neonDim, fontSize: 13)),
        const SizedBox(height: 20),
        Wrap(spacing: 12, runSpacing: 12, children: [
          FilledButton(key: const ValueKey('save'), onPressed: _save, child: const Text('Speichern')),
          OutlinedButton(onPressed: _test, child: const Text('Verbindung testen')),
        ]),
        const SizedBox(height: 16),
        Text(_status, key: const ValueKey('status'), style: const TextStyle(color: neonText)),
      ]),
    );
  }
}
