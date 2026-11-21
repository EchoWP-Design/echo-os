// Startseite: ECHO-Chat, Kodi, Einstellungen und alle Streaming-Dienste als Kacheln.
// Installierte Apps starten direkt, fehlende öffnen den App-Store.
import 'package:flutter/material.dart';

import '../apps.dart';
import '../services.dart';
import '../widgets/neon.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({
    super.key,
    required this.services,
    required this.apps,
    required this.onOpenChat,
    required this.onOpenSettings,
  });

  final List<StreamingService> services;
  final AppsApi apps;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenSettings;

  @override
  State<HomeScreen> createState() => HomeScreenState();
}

class HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  Map<String, String> installed = {};
  bool tv = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    refresh();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  // Nach der Rückkehr aus dem App-Store neu einlesen, ob die App jetzt installiert ist
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) refresh();
  }

  Future<void> refresh() async {
    final apps = await widget.apps.installed();
    final isTv = await widget.apps.isTv();
    if (!mounted) return;
    setState(() {
      installed = apps;
      tv = isTv || apps.isEmpty;
    });
  }

  void _toast(String text) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(text), duration: const Duration(seconds: 4)));
  }

  Future<void> openService(StreamingService s) async {
    final pkg = findPackage(s, installed, tv: tv);
    if (pkg != null) {
      if (!await widget.apps.launch(pkg)) _toast('${s.name} ließ sich nicht starten.');
      return;
    }
    final store = storePackage(s, tv: tv);
    if (store != null && await widget.apps.openStore(store)) {
      _toast('${s.name} ist noch nicht installiert – der App-Store wird geöffnet.');
    } else {
      _toast('${s.name} ist noch nicht installiert. Bitte im App-Store suchen.');
    }
  }

  Future<void> openKodi() async {
    if (installed.containsKey(kodiPackage) && await widget.apps.launch(kodiPackage)) return;
    _toast('Kodi ist nicht installiert. Auf dem Fire TV über die Downloader-App von kodi.tv installieren.');
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.of(context).size.width;
    final columns = width > 1100 ? 6 : (width > 700 ? 4 : 3);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(32, 20, 32, 0),
          child: CustomScrollView(slivers: [
            SliverToBoxAdapter(
              child: Row(children: [
                const NeonTitle('ECHO', size: 36),
                const SizedBox(width: 14),
                Flexible(
                  child: Text('Streaming · Kodi · KI',
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: neonMagenta, letterSpacing: 4, fontSize: 16, shadows: const [
                        Shadow(color: neonMagenta, blurRadius: 8),
                      ])),
                ),
              ]),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 18)),
            SliverGrid.count(
              crossAxisCount: columns,
              mainAxisSpacing: 18,
              crossAxisSpacing: 18,
              childAspectRatio: 1.6,
              children: [
                NeonTile(
                  key: const ValueKey('tile-echo'),
                  autofocus: true,
                  glow: neonMagenta,
                  onPressed: widget.onOpenChat,
                  child: const _ActionTile(icon: Icons.graphic_eq, label: 'ECHO', sub: 'KI-Chat', color: Color(0xFF3A0070)),
                ),
                NeonTile(
                  key: const ValueKey('tile-kodi'),
                  onPressed: openKodi,
                  child: const _ActionTile(icon: Icons.movie_filter, label: 'Kodi', sub: 'Filme & Serien', color: Color(0xFF0B4F6C)),
                ),
                NeonTile(
                  key: const ValueKey('tile-settings'),
                  onPressed: widget.onOpenSettings,
                  child: const _ActionTile(icon: Icons.settings, label: 'Einstellungen', sub: 'Pi & Claude', color: Color(0xFF26203A)),
                ),
              ],
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 26)),
            const SliverToBoxAdapter(
              child: Text('STREAMING',
                  style: TextStyle(color: neonCyan, letterSpacing: 6, fontSize: 15, shadows: [Shadow(color: neonCyan, blurRadius: 6)])),
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 12)),
            SliverGrid.count(
              crossAxisCount: columns,
              mainAxisSpacing: 18,
              crossAxisSpacing: 18,
              childAspectRatio: 1.6,
              children: [
                for (final s in widget.services)
                  NeonTile(
                    key: ValueKey('tile-${s.id}'),
                    onPressed: () => openService(s),
                    child: _ServiceTile(service: s, installed: findPackage(s, installed, tv: tv) != null),
                  ),
              ],
            ),
            const SliverToBoxAdapter(child: SizedBox(height: 32)),
          ]),
        ),
      ),
    );
  }
}

class _ActionTile extends StatelessWidget {
  const _ActionTile({required this.icon, required this.label, required this.sub, required this.color});

  final IconData icon;
  final String label;
  final String sub;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      color: color,
      padding: const EdgeInsets.all(8),
      child: FittedBox(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, size: 40, color: neonCyan),
          const SizedBox(height: 4),
          Text(label, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Colors.white)),
          Text(sub, style: const TextStyle(fontSize: 13, color: neonDim)),
        ]),
      ),
    );
  }
}

class _ServiceTile extends StatelessWidget {
  const _ServiceTile({required this.service, required this.installed});

  final StreamingService service;
  final bool installed;

  @override
  Widget build(BuildContext context) {
    return Stack(fit: StackFit.expand, children: [
      Image.asset(
        'assets/tiles/${service.id}.png',
        fit: BoxFit.cover,
        errorBuilder: (context, error, stack) => Container(
          color: Color(colorValue(service.color)),
          alignment: Alignment.center,
          child: Text(service.name, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 20)),
        ),
      ),
      if (!installed)
        Positioned(
          right: 6,
          bottom: 6,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(color: const Color(0xCC000000), borderRadius: BorderRadius.circular(6)),
            child: const Text('installieren', style: TextStyle(fontSize: 12, color: neonText)),
          ),
        ),
    ]);
  }
}
