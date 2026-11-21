// Echo-App: Neon-Startseite für Fire TV / Android TV (Schritt 2) – später auch
// Fernbedienung für den Echo-OS-Pi auf dem Handy (Schritt 3).
import 'package:flutter/material.dart';

import 'apps.dart';
import 'screens/chat_screen.dart';
import 'screens/home_screen.dart';
import 'screens/intro_screen.dart';
import 'screens/settings_screen.dart';
import 'services.dart';
import 'settings.dart';
import 'widgets/neon.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const EchoApp());
}

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
    if (!mounted) return;
    setState(() {
      _services = services;
      _settings = settings;
    });
  }

  void _openSettings() {
    _nav.currentState?.push(MaterialPageRoute<void>(
      builder: (_) => SettingsScreen(settings: _settings),
    ));
  }

  void _openChat() {
    _nav.currentState?.push(MaterialPageRoute<void>(
      builder: (_) => ChatScreen(settings: _settings, onOpenSettings: _openSettings),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Echo',
      debugShowCheckedModeBanner: false,
      theme: neonTheme(),
      navigatorKey: _nav,
      home: _intro
          ? IntroScreen(onDone: () => setState(() => _intro = false))
          : HomeScreen(
              key: ValueKey(_services.length),
              services: _services,
              apps: widget.apps,
              onOpenChat: _openChat,
              onOpenSettings: _openSettings,
            ),
    );
  }
}
