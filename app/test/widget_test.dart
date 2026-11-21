// Tests der Echo-App (laufen in GitHub Actions vor jedem Build).
import 'dart:convert';

import 'package:echo_app/apps.dart';
import 'package:echo_app/chat.dart';
import 'package:echo_app/screens/chat_screen.dart';
import 'package:echo_app/screens/home_screen.dart';
import 'package:echo_app/screens/intro_screen.dart';
import 'package:echo_app/screens/settings_screen.dart';
import 'package:echo_app/services.dart';
import 'package:echo_app/settings.dart';
import 'package:echo_app/widgets/neon.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const netflix = StreamingService(
  id: 'netflix',
  name: 'Netflix',
  color: '#b20710',
  tv: ['com.netflix.ninja'],
  mobile: ['com.netflix.mediaclient'],
);
const ard = StreamingService(
  id: 'ard',
  name: 'ARD Mediathek',
  color: '#003480',
  tv: ['de.swr.avp.ard.tv'],
  mobile: ['de.swr.avp.ard'],
  labels: ['ARD Mediathek', 'ARD'],
);
const plus = StreamingService(id: 'disneyplus', name: 'Disney+', color: '#113ccf', tv: ['com.disney.disneyplus']);

/// Simulierte Android-Seite: merkt sich alle Aufrufe.
class FakeAndroid {
  FakeAndroid(this.installed, {this.tv = true});

  final Map<String, String> installed;
  final bool tv;
  final calls = <MethodCall>[];
  static const channel = MethodChannel('echoos/apps');

  void install(WidgetTester tester) {
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      switch (call.method) {
        case 'installed':
          return installed;
        case 'isTv':
          return tv;
        case 'launch':
          return installed.containsKey((call.arguments as Map)['package']);
        case 'store':
          return true;
      }
      return null;
    });
  }

  List<String> args(String method) =>
      [for (final c in calls) if (c.method == method) (c.arguments as Map)['package'] as String];
}

void main() {
  group('Streaming-Dienste', () {
    test('services.json der App enthält alle Dienste mit Android-Paketen', () async {
      TestWidgetsFlutterBinding.ensureInitialized();
      final list = await loadServices();
      expect(list.length, greaterThanOrEqualTo(18));
      expect(list.map((s) => s.id), containsAll(['netflix', 'primevideo', 'disneyplus', 'ard', 'zdf']));
      expect(list.every((s) => s.tv.isNotEmpty || s.mobile.isNotEmpty), isTrue);
    });

    test('Fernseher bevorzugt die TV-App, Handy die Handy-App', () {
      final both = {'com.netflix.ninja': 'Netflix', 'com.netflix.mediaclient': 'Netflix'};
      expect(findPackage(netflix, both, tv: true), 'com.netflix.ninja');
      expect(findPackage(netflix, both, tv: false), 'com.netflix.mediaclient');
      expect(findPackage(netflix, {'com.netflix.mediaclient': 'Netflix'}, tv: true), 'com.netflix.mediaclient');
    });

    test('Unbekannter Paketname wird über den App-Namen gefunden', () {
      expect(findPackage(ard, {'de.ard.neu': 'ARD'}, tv: true), 'de.ard.neu');
      expect(findPackage(plus, {'x.y': 'Disney Plus'}, tv: true), 'x.y');
      expect(findPackage(netflix, {'x.y': 'Netflix Kids Fake'}, tv: true), isNull);
    });

    test('App-Store-Paket passend zum Gerät', () {
      expect(storePackage(netflix, tv: true), 'com.netflix.ninja');
      expect(storePackage(netflix, tv: false), 'com.netflix.mediaclient');
      expect(storePackage(plus, tv: false), 'com.disney.disneyplus');
    });

    test('Farben werden gelesen', () {
      expect(colorValue('#b20710'), 0xffb20710);
      expect(colorValue('kaputt'), 0xff333333);
    });
  });

  group('ECHO-Chat', () {
    test('Pi-Adresse wird ergänzt', () {
      expect(piBase('192.168.178.193').toString(), 'http://192.168.178.193:8090');
      expect(piBase('echo-os:9000').toString(), 'http://echo-os:9000');
      expect(piBase('http://10.0.0.5:8090/').toString(), 'http://10.0.0.5:8090');
    });

    test('Pi: Nachricht mit Zugangscode senden', () async {
      late http.Request seen;
      final client = MockClient((req) async {
        seen = req;
        return http.Response(jsonEncode({'reply': 'Läuft: Dark S01E04', 'actions': ['play']}), 200,
            headers: {'content-type': 'application/json; charset=utf-8'});
      });
      final pi = PiBackend('192.168.178.193', 'abcd1234', client: client);
      expect(await pi.send('Spiel Dark'), 'Läuft: Dark S01E04');
      expect(seen.url.toString(), 'http://192.168.178.193:8090/api/chat');
      expect(seen.headers['Authorization'], 'Bearer abcd1234');
      expect(jsonDecode(seen.body), {'message': 'Spiel Dark'});
    });

    test('Pi: falscher Code wird verständlich gemeldet', () async {
      final client = MockClient((req) async => http.Response('{"fehler":"Code falsch"}', 401));
      expect(await PiBackend('pi', 'x', client: client).send('Hallo'), contains('Zugangscode'));
    });

    test('Claude: Schlüssel im Kopf, Antworttext wird gelesen', () async {
      late http.Request seen;
      final client = MockClient((req) async {
        seen = req;
        return http.Response(
            jsonEncode({
              'content': [
                {'type': 'text', 'text': 'Hallo, ich bin ECHO.'}
              ]
            }),
            200,
            headers: {'content-type': 'application/json; charset=utf-8'});
      });
      final c = ClaudeBackend('sk-ant-test', client: client);
      expect(await c.send('Wer bist du?'), 'Hallo, ich bin ECHO.');
      expect(seen.headers['x-api-key'], 'sk-ant-test');
      expect(seen.headers['anthropic-version'], '2023-06-01');
      final body = jsonDecode(seen.body) as Map<String, dynamic>;
      expect(body['model'], 'claude-haiku-5-5');
      expect((body['messages'] as List).last, {'role': 'user', 'content': 'Wer bist du?'});
    });

    test('Claude: abgelehnter Schlüssel', () async {
      final client = MockClient((req) async =>
          http.Response('{"type":"error","error":{"type":"authentication_error","message":"invalid x-api-key"}}', 401));
      expect(await ClaudeBackend('falsch', client: client).send('Hi'), contains('Schlüssel'));
    });

    test('Auswahl: Pi erreichbar → Pi, sonst Claude, sonst nichts', () async {
      final up = MockClient((req) async => http.Response('{}', 200));
      final down = MockClient((req) async => throw http.ClientException('weg'));
      final both = EchoSettings(piHost: 'pi', piToken: 't', claudeKey: 'k');
      expect(await pickBackend(both, client: up), isA<PiBackend>());
      expect(await pickBackend(both, client: down), isA<ClaudeBackend>());
      expect(await pickBackend(EchoSettings(piHost: 'pi', piToken: 't'), client: down), isNull);
      expect(await pickBackend(EchoSettings(), client: up), isNull);
    });
  });

  group('Oberfläche', () {
    Future<FakeAndroid> pumpHome(WidgetTester tester, Map<String, String> installed,
        {bool tv = true, VoidCallback? onChat}) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final android = FakeAndroid(installed, tv: tv)..install(tester);
      await tester.pumpWidget(MaterialApp(
        theme: neonTheme(),
        home: HomeScreen(
          services: const [netflix, ard, plus],
          apps: const AppsApi(),
          onOpenChat: onChat ?? () {},
          onOpenSettings: () {},
        ),
      ));
      await tester.pumpAndSettle();
      return android;
    }

    testWidgets('Startseite zeigt ECHO, Kodi, Einstellungen und alle Dienste', (tester) async {
      await pumpHome(tester, {'com.netflix.ninja': 'Netflix'});
      for (final id in ['echo', 'kodi', 'settings', 'netflix', 'ard', 'disneyplus']) {
        expect(find.byKey(ValueKey('tile-$id')), findsOneWidget, reason: id);
      }
      // Nur fehlende Dienste tragen den Hinweis "installieren"
      expect(find.text('installieren'), findsNWidgets(2));
    });

    testWidgets('Installierter Dienst startet die TV-App', (tester) async {
      final android = await pumpHome(tester, {'com.netflix.ninja': 'Netflix', 'com.netflix.mediaclient': 'Netflix'});
      await tester.tap(find.byKey(const ValueKey('tile-netflix')));
      await tester.pumpAndSettle();
      expect(android.args('launch'), ['com.netflix.ninja']);
      expect(android.args('store'), isEmpty);
    });

    testWidgets('Fehlender Dienst öffnet den App-Store', (tester) async {
      final android = await pumpHome(tester, {});
      await tester.tap(find.byKey(const ValueKey('tile-ard')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));
      expect(android.args('store'), ['de.swr.avp.ard.tv']);
      expect(find.textContaining('App-Store'), findsOneWidget);
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
    });

    testWidgets('Kodi starten oder Hinweis zeigen', (tester) async {
      final android = await pumpHome(tester, {kodiPackage: 'Kodi'});
      await tester.tap(find.byKey(const ValueKey('tile-kodi')));
      await tester.pumpAndSettle();
      expect(android.args('launch'), [kodiPackage]);
    });

    testWidgets('Fernbedienung: Pfeil rechts + OK startet die nächste Kachel', (tester) async {
      var chats = 0;
      final android = await pumpHome(tester, {kodiPackage: 'Kodi'}, onChat: () => chats++);
      // ECHO-Kachel hat den Fokus: OK öffnet den Chat
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(chats, 1);
      // Rechts → Kodi, OK startet Kodi
      await tester.sendKeyEvent(LogicalKeyboardKey.arrowRight);
      await tester.pumpAndSettle();
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(android.args('launch'), [kodiPackage]);
    });

    test('OK-Taste der Fire-TV-Fernbedienung (Select) löst Kacheln aus', () {
      expect(activateShortcuts[const SingleActivator(LogicalKeyboardKey.select)], isA<ActivateIntent>());
    });

    testWidgets('Intro läuft und geht danach weiter', (tester) async {
      var done = 0;
      await tester.pumpWidget(MaterialApp(
        home: IntroScreen(onDone: () => done++, duration: const Duration(seconds: 2)),
      ));
      await tester.pump(const Duration(milliseconds: 500));
      expect(done, 0);
      await tester.pump(const Duration(seconds: 2));
      expect(done, 1);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('Chat ohne Einrichtung verweist auf die Einstellungen', (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: ChatScreen(settings: EchoSettings(), picker: (_) async => null, onOpenSettings: () {}),
      ));
      await tester.pumpAndSettle();
      expect(find.textContaining('noch nicht eingerichtet'), findsWidgets);
    });

    testWidgets('Chat sendet über das gewählte Backend', (tester) async {
      final client = MockClient((req) async => http.Response(
          jsonEncode({'reply': 'Pause gedrückt.'}), 200,
          headers: {'content-type': 'application/json; charset=utf-8'}));
      await tester.pumpWidget(MaterialApp(
        home: ChatScreen(
          settings: EchoSettings(),
          picker: (_) async => PiBackend('pi', 't', client: client),
          onOpenSettings: () {},
        ),
      ));
      await tester.pumpAndSettle();
      expect(find.text('über Echo-OS-Pi'), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('chat-input')), 'Pause');
      await tester.tap(find.byKey(const ValueKey('chat-send')));
      await tester.pumpAndSettle();
      expect(find.text('Pause gedrückt.'), findsOneWidget);
    });

    testWidgets('Einstellungen speichern Adresse, Code und Schlüssel', (tester) async {
      tester.view.physicalSize = const Size(1920, 1080);
      tester.view.devicePixelRatio = 1.0;
      addTearDown(tester.view.reset);
      final settings = EchoSettings();
      EchoSettings? saved;
      await tester.pumpWidget(MaterialApp(
        home: SettingsScreen(settings: settings, onSave: (s) async => saved = s),
      ));
      await tester.enterText(find.byKey(const ValueKey('pi-host')), ' 192.168.178.193 ');
      await tester.enterText(find.byKey(const ValueKey('pi-token')), 'abcd1234');
      await tester.enterText(find.byKey(const ValueKey('claude-key')), 'sk-ant-x');
      await tester.tap(find.byKey(const ValueKey('save')));
      await tester.pumpAndSettle();
      expect(saved, isNotNull);
      expect(settings.piHost, '192.168.178.193');
      expect(settings.hasPi && settings.hasClaude, isTrue);
      expect(find.text('Gespeichert.'), findsOneWidget);
    });
  });
}
