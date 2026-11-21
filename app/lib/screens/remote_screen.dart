// Handy-Modus: Fernbedienung für den Echo-OS-Pi (Status, Wiedergabe, Streaming,
// Bibliothek, Updates, Sicherheit, Neustart) über den ECHO-Agenten.
import 'dart:async';

import 'package:flutter/material.dart';

import '../pi_api.dart';
import '../services.dart' show colorValue;
import '../settings.dart';
import '../widgets/neon.dart';

class RemoteScreen extends StatefulWidget {
  const RemoteScreen({
    super.key,
    required this.settings,
    required this.onOpenChat,
    required this.onOpenSettings,
    required this.onOpenApps,
    this.api,
    this.refreshEvery = const Duration(seconds: 10),
  });

  final EchoSettings settings;
  final VoidCallback onOpenChat;
  final Future<void> Function() onOpenSettings;
  final VoidCallback onOpenApps;

  /// Zum Testen austauschbar; sonst aus den Einstellungen.
  final PiApi? api;
  final Duration refreshEvery;

  @override
  State<RemoteScreen> createState() => _RemoteScreenState();
}

class _RemoteScreenState extends State<RemoteScreen> {
  PiApi? _api;
  Map<String, dynamic>? _status;
  String? _error;
  bool _busy = false;
  List<Map<String, dynamic>> _services = [];
  double _volume = 50;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _setup();
    _timer = Timer.periodic(widget.refreshEvery, (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _setup() {
    final s = widget.settings;
    _api = widget.api ?? (s.hasPi ? PiApi(s.piHost, s.piToken) : null);
    _status = null;
    _error = null;
    _services = [];
    _refresh();
    _loadServices();
  }

  Future<void> _loadServices() async {
    final api = _api;
    if (api == null) return;
    try {
      final list = await api.services();
      if (mounted) setState(() => _services = list);
    } catch (_) {}
  }

  Future<void> _refresh() async {
    final api = _api;
    if (api == null) {
      if (mounted) setState(() {});
      return;
    }
    try {
      final st = await api.status();
      if (!mounted) return;
      setState(() {
        _status = st;
        _error = null;
      });
    } on PiAuthException {
      if (mounted) setState(() => _error = 'Der Zugangscode stimmt nicht – bitte in den Einstellungen prüfen.');
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'Pi nicht erreichbar. Ist das Handy im Heimnetz-WLAN und der Pi eingeschaltet?');
      }
    }
  }

  Future<void> _act(String action, {Map<String, Object?> extra = const {}, String? confirm}) async {
    final api = _api;
    if (api == null || _busy) return;
    if (confirm != null) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          content: Text(confirm),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Abbrechen')),
            FilledButton(
                key: const ValueKey('confirm-yes'),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Ja')),
          ],
        ),
      );
      if (ok != true) return;
    }
    setState(() => _busy = true);
    String text;
    try {
      text = describeResult(await api.action(action, extra));
    } on PiAuthException {
      text = '⚠ Zugangscode falsch.';
    } catch (_) {
      text = '⚠ Keine Verbindung zum Pi.';
    }
    if (!mounted) return;
    setState(() => _busy = false);
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text), duration: const Duration(seconds: 4)));
    _refresh();
  }

  Future<void> _openSettings() async {
    await widget.onOpenSettings();
    if (mounted) setState(_setup);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: neonBg,
        title: const NeonTitle('ECHO', size: 26),
        actions: [
          IconButton(tooltip: 'Apps auf diesem Handy', icon: const Icon(Icons.apps), onPressed: widget.onOpenApps),
          IconButton(
              key: const ValueKey('open-chat'),
              tooltip: 'ECHO-Chat',
              icon: const Icon(Icons.graphic_eq),
              onPressed: widget.onOpenChat),
          IconButton(tooltip: 'Einstellungen', icon: const Icon(Icons.settings), onPressed: _openSettings),
        ],
      ),
      body: _api == null ? _setupHint() : RefreshIndicator(onRefresh: _refresh, child: _body()),
    );
  }

  Widget _setupHint() {
    return ListView(padding: const EdgeInsets.all(24), children: [
      const Text('Fernbedienung für deinen Echo-OS-Pi',
          style: TextStyle(color: neonCyan, fontSize: 20, fontWeight: FontWeight.bold)),
      const SizedBox(height: 10),
      const Text(
        'Trage in den Einstellungen die Adresse und den Zugangscode deines Pi ein. Beides zeigt der Pi '
        'beim Start unten rechts auf dem Fernseher.',
        style: TextStyle(color: neonText, fontSize: 16),
      ),
      const SizedBox(height: 20),
      Align(
        alignment: Alignment.centerLeft,
        child: FilledButton(
            key: const ValueKey('setup'), onPressed: _openSettings, child: const Text('Einstellungen öffnen')),
      ),
    ]);
  }

  Widget _section(String title, List<Widget> children) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 22),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title,
            style: const TextStyle(
                color: neonCyan, letterSpacing: 4, fontSize: 13, shadows: [Shadow(color: neonCyan, blurRadius: 6)])),
        const SizedBox(height: 10),
        ...children,
      ]),
    );
  }

  Widget _ctrl(IconData icon, String tip, String action, {int? value, Key? key}) {
    return IconButton.filledTonal(
      key: key,
      tooltip: tip,
      iconSize: 30,
      onPressed: _busy ? null : () => _act('control', extra: {'command': action, 'value': value}),
      icon: Icon(icon),
    );
  }

  Widget _body() {
    final st = _status;
    final sys = (st?['system'] as Map?) ?? const {};
    final upd = (st?['updates'] as Map?) ?? const {};
    final sec = (st?['security'] as Map?) ?? const {};
    final warn = (sec['warnungen'] as List?) ?? const [];
    final drives = ((st?['drives'] as List?) ?? const []).map((d) => d.toString().split('/').last).join(', ');
    return ListView(padding: const EdgeInsets.fromLTRB(20, 16, 20, 32), children: [
      if (_error != null)
        Container(
          key: const ValueKey('error'),
          padding: const EdgeInsets.all(12),
          margin: const EdgeInsets.only(bottom: 16),
          decoration: BoxDecoration(border: Border.all(color: neonMagenta), borderRadius: BorderRadius.circular(10)),
          child: Text(_error!, style: const TextStyle(color: neonText)),
        ),
      _section('LÄUFT', [
        Text(st == null ? '…' : nowPlayingText(st),
            key: const ValueKey('now-playing'),
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white)),
        const SizedBox(height: 6),
        if (st != null)
          Text(
            [
              if (sys['temperatur_c'] != null) '${sys['temperatur_c']} °C',
              upd['anzahl'] == null ? 'Updates: –' : 'Updates: ${upd['anzahl']} offen',
              if (upd['neustart_noetig'] == true) 'Neustart nötig',
              warn.isEmpty ? 'Sicherheit: in Ordnung' : 'Sicherheit: ${warn.length} Warnung(en)',
              if (drives.isNotEmpty) 'Laufwerke: $drives',
            ].join(' · '),
            style: TextStyle(color: warn.isEmpty ? neonDim : const Color(0xFFFFD23F)),
          ),
      ]),
      _section('WIEDERGABE', [
        Wrap(spacing: 10, runSpacing: 10, children: [
          _ctrl(Icons.skip_previous, 'Vorherige', 'previous'),
          _ctrl(Icons.replay_10, '10 s zurück', 'back', value: 10),
          _ctrl(Icons.play_arrow, 'Wiedergabe / Pause', 'play_pause', key: const ValueKey('play-pause')),
          _ctrl(Icons.forward_30, '30 s vor', 'forward', value: 30),
          _ctrl(Icons.skip_next, 'Nächste', 'next'),
          _ctrl(Icons.stop, 'Stopp', 'stop'),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          IconButton(tooltip: 'Ton aus/an', icon: const Icon(Icons.volume_off), onPressed: () => _act('control', extra: {'command': 'mute'})),
          Expanded(
            child: Slider(
              value: _volume,
              min: 0,
              max: 100,
              divisions: 20,
              label: '${_volume.round()} %',
              onChanged: (v) => setState(() => _volume = v),
              onChangeEnd: (v) => _act('control', extra: {'command': 'volume', 'value': v.round()}),
            ),
          ),
        ]),
        Wrap(spacing: 10, runSpacing: 10, children: [
          OutlinedButton.icon(
              onPressed: () => _act('control', extra: {'command': 'subtitles'}),
              icon: const Icon(Icons.subtitles),
              label: const Text('Untertitel')),
          OutlinedButton.icon(
              onPressed: () => _act('control', extra: {'command': 'audio_track'}),
              icon: const Icon(Icons.audiotrack),
              label: const Text('Tonspur')),
          FilledButton.icon(
              key: const ValueKey('to-kodi'),
              onPressed: () => _act('back_to_kodi'),
              icon: const Icon(Icons.home),
              label: const Text('Zu Kodi')),
        ]),
      ]),
      if (_services.isNotEmpty)
        _section('STREAMING AUF DEM PI', [
          Wrap(spacing: 8, runSpacing: 8, children: [
            for (final s in _services)
              ActionChip(
                key: ValueKey('pi-${s['id']}'),
                backgroundColor: Color(colorValue((s['color'] ?? '#333333').toString())),
                label: Text((s['name'] ?? s['id']).toString(), style: const TextStyle(color: Colors.white)),
                onPressed: () => _act('launch', extra: {'service': s['id']}),
              ),
          ]),
        ]),
      _section('SYSTEM', [
        Wrap(spacing: 10, runSpacing: 10, children: [
          OutlinedButton(onPressed: () => _act('scan'), child: const Text('Bibliothek aktualisieren')),
          OutlinedButton(onPressed: () => _act('check_updates'), child: const Text('Updates prüfen')),
          OutlinedButton(onPressed: () => _act('security'), child: const Text('Sicherheit prüfen')),
          OutlinedButton(
              onPressed: () => _act('apply_updates', confirm: 'Alle Updates jetzt auf dem Pi installieren?'),
              child: const Text('Updates installieren')),
          OutlinedButton(
              key: const ValueKey('reboot'),
              onPressed: () => _act('reboot', confirm: 'Echo-OS jetzt neu starten?'),
              child: const Text('Neustart')),
        ]),
      ]),
    ]);
  }
}
