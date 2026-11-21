// ECHO-Chat: wählt beim Öffnen den Pi oder Claude und zeigt, womit gerade gesprochen wird.
import 'package:flutter/material.dart';

import '../chat.dart';
import '../settings.dart';
import '../widgets/neon.dart';

typedef BackendPicker = Future<ChatBackend?> Function(EchoSettings settings);

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key, required this.settings, this.picker = pickBackend, required this.onOpenSettings});

  final EchoSettings settings;
  final BackendPicker picker;
  final VoidCallback onOpenSettings;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _Msg {
  _Msg(this.text, this.mine);
  final String text;
  final bool mine;
}

class _ChatScreenState extends State<ChatScreen> {
  final _input = TextEditingController();
  final _scroll = ScrollController();
  final _messages = <_Msg>[];
  ChatBackend? _backend;
  bool _connecting = true;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final b = await widget.picker(widget.settings);
    if (!mounted) return;
    setState(() {
      _backend = b;
      _connecting = false;
      _messages.add(_Msg(
          b == null
              ? 'ECHO ist noch nicht eingerichtet. Trage in den Einstellungen die Adresse und den Zugangscode deines Echo-OS-Pi ein – oder einen eigenen Claude-API-Schlüssel.'
              : b is PiBackend
                  ? 'Verbunden mit deinem Echo-OS-Pi. Ich kann Kodi steuern, in der Bibliothek suchen und nach Updates schauen.'
                  : 'Der Pi ist nicht erreichbar – ich antworte direkt über Claude. Steuern kann ich von hier aus nichts.',
          false));
    });
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    final b = _backend;
    if (text.isEmpty || b == null || _busy) return;
    _input.clear();
    setState(() {
      _messages.add(_Msg(text, true));
      _busy = true;
    });
    _scrollDown();
    String reply;
    try {
      reply = await b.send(text);
    } catch (e) {
      reply = 'Keine Verbindung (${e.runtimeType}). Bitte Netzwerk und Einstellungen prüfen.';
    }
    if (!mounted) return;
    setState(() {
      _messages.add(_Msg(reply, false));
      _busy = false;
    });
    _scrollDown();
  }

  void _scrollDown() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  @override
  Widget build(BuildContext context) {
    final status = _connecting
        ? 'verbinde …'
        : _backend == null
            ? 'nicht eingerichtet'
            : 'über ${_backend!.label}';
    return Scaffold(
      appBar: AppBar(
        backgroundColor: neonBg,
        title: Row(children: [
          const NeonTitle('ECHO', size: 26),
          const SizedBox(width: 12),
          Flexible(child: Text(status, overflow: TextOverflow.ellipsis, style: const TextStyle(color: neonDim, fontSize: 15))),
        ]),
        actions: [
          IconButton(
            tooltip: 'Einstellungen',
            icon: const Icon(Icons.settings),
            onPressed: widget.onOpenSettings,
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(20),
            itemCount: _messages.length + (_busy ? 1 : 0),
            itemBuilder: (context, i) {
              if (i == _messages.length) {
                return const Padding(
                  padding: EdgeInsets.all(8),
                  child: Text('ECHO denkt nach …', style: TextStyle(color: neonDim)),
                );
              }
              final m = _messages[i];
              return Align(
                alignment: m.mine ? Alignment.centerRight : Alignment.centerLeft,
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 760),
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  decoration: BoxDecoration(
                    color: m.mine ? const Color(0x22FF28C8) : const Color(0x1400F0FF),
                    border: Border.all(color: m.mine ? neonMagenta : const Color(0x8800F0FF)),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: SelectableText(m.text, style: const TextStyle(fontSize: 17, color: neonText)),
                ),
              );
            },
          ),
        ),
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 16),
            child: Row(children: [
              Expanded(
                child: TextField(
                  key: const ValueKey('chat-input'),
                  controller: _input,
                  enabled: _backend != null,
                  textInputAction: TextInputAction.send,
                  onSubmitted: (_) => _send(),
                  decoration: const InputDecoration(hintText: 'Nachricht an ECHO …'),
                ),
              ),
              const SizedBox(width: 12),
              FilledButton(
                key: const ValueKey('chat-send'),
                onPressed: _backend == null || _busy ? null : _send,
                child: const Text('SENDEN'),
              ),
            ]),
          ),
        ),
      ]),
    );
  }
}
