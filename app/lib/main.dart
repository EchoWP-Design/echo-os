// Echo-App: auf dem Fernseher Neon-Startseite mit Streaming-Kacheln, Kodi und ECHO-Chat
// (Schritt 2), auf dem Handy Fernbedienung für den Echo-OS-Pi (Schritt 3).
import 'package:flutter/material.dart';

import 'apps.dart';
import 'screens/chat_screen.dart';
import 'screens/home_screen.dart';
import 'screens/intro_screen.dart';
import 'screens/remote_screen.dart';
import 'screens/settings_screen.dart';
import 'services.dart';
import 'settings.dart';
import 'widgets/neon.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const EchoApp());
}

/// Fernseher-Ansicht? Einstellung schlägt Erkennung.
bool useTvLayout(String viewMode, {required bool deviceIsTv}) =>
    viewMode == 'tv' || (viewMode != 'phone' && deviceIsTv);

class EchoApp extends StatefulWidget {
  const EchoApp({super.key, this.apps = const AppsApi(), this.showIntro = true});

  final AppsApi apps;
  final bool showIntro;

  @override
  State<EchoApp> createState() => _EchoAppState();
}

class _EchoAppState extends State<EchoApp> {
  final _nav = GlobalKey<NavigatorState>();
  late bool _intro = widget.showIntro;
  List<StreamingService> _services = const [];
  EchoSettings _settings = EchoSettings();
  bool _deviceIsTv = false;
  bool? _tv; // null, solange noch nicht feststeht, welches Gerät es ist
  int _generation = 0;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    List<StreamingService> services = const [];
    try {
      services = await loadServices();
    } catch (_) {}
    EchoSettings settings = EchoSettings();
    try {
      settings = await EchoSettings.load();
    } catch (_) {}
    final isTv = await widget.apps.isTv();
    if (!mounted) return;
    setState(() {
      _services = services;
      _settings = settings;
      _deviceIsTv = isTv;
      _tv = useTvLayout(settings.viewMode, deviceIsTv: isTv);
    });
  }

  Future<void> _openSettings() async {
    await _nav.currentState?.push(MaterialPageRoute<void>(
      builder: (_) => SettingsScreen(settings: _settings),
    ));
    if (!mounted) return;
    final tv = useTvLayout(_settings.viewMode, deviceIsTv: _deviceIsTv);
    if (tv != _tv) {
      setState(() {
        _tv = tv;
        _intro = false;
        _generation++;
      });
    }
  }

  void _openChat() {
    _nav.currentState?.push(MaterialPageRoute<void>(
      builder: (_) => ChatScreen(settings: _settings, onOpenSettings: _openSettings),
    ));
  }

  Widget _tiles() => HomeScreen(
        key: ValueKey('home-${_services.length}-$_generation'),
        services: _services,
        apps: widget.apps,
        onOpenChat: _openChat,
        onOpenSettings: _openSettings,
      );

  void _openApps() {
    _nav.currentState?.push(MaterialPageRoute<void>(builder: (_) => _tiles()));
  }

  Widget _home() {
    final tv = _tv;
    if (tv == null) return const Scaffold(backgroundColor: neonBg);
    if (!tv) {
      return RemoteScreen(
        key: ValueKey('remote-$_generation'),
        settings: _settings,
        onOpenChat: _openChat,
        onOpenSettings: _openSettings,
        onOpenApps: _openApps,
      );
    }
    if (_intro) return IntroScreen(onDone: () => setState(() => _intro = false));
    return _tiles();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Echo',
      debugShowCheckedModeBanner: false,
      theme: neonTheme(),
      navigatorKey: _nav,
      home: _home(),
    );
  }
}
