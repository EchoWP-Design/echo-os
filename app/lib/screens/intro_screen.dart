// Neon-Intro wie der Echo-OS-Bootscreen: Synthwave-Hintergrund, fahrendes
// Gitter, Chrom-Logo und Tron-Lichtspur. Grafiken stammen aus gen_bootscreen.py.
import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';

class IntroScreen extends StatefulWidget {
  const IntroScreen({super.key, required this.onDone, this.duration = const Duration(milliseconds: 3800)});

  final VoidCallback onDone;
  final Duration duration;

  @override
  State<IntroScreen> createState() => _IntroScreenState();
}

class _IntroScreenState extends State<IntroScreen> with SingleTickerProviderStateMixin {
  static const frames = 24;
  late final AnimationController _anim =
      AnimationController(vsync: this, duration: const Duration(seconds: 1))..repeat();
  Timer? _timer;
  final _start = DateTime.now();
  bool _done = false;

  @override
  void initState() {
    super.initState();
    _timer = Timer(widget.duration, _finish);
  }

  void _finish() {
    if (_done || !mounted) return;
    _done = true;
    widget.onDone();
  }

  @override
  void dispose() {
    _timer?.cancel();
    _anim.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Focus(
      autofocus: true,
      // Jede Taste überspringt das Intro
      onKeyEvent: (node, event) {
        _finish();
        return KeyEventResult.handled;
      },
      child: GestureDetector(
        onTap: _finish,
        child: LayoutBuilder(builder: (context, box) {
          final w = box.maxWidth, h = box.maxHeight;
          return AnimatedBuilder(
            animation: _anim,
            builder: (context, _) {
              final t = DateTime.now().difference(_start).inMilliseconds / 1000.0;
              final frame = (t * 25).floor() % frames;
              final logoIn = math.min(1.0, t / 1.2);
              final pulse = 0.92 + 0.08 * math.sin(t * 3);
              final streakW = w * 0.28;
              final streakX = ((t * 0.45) % 1.0) * (w + 2 * streakW) - streakW;
              return Stack(children: [
                Positioned.fill(child: Image.asset('assets/boot/background.png', fit: BoxFit.fill)),
                Positioned(
                  left: 0,
                  right: 0,
                  top: h * 400 / 720,
                  height: h * 320 / 720,
                  child: Image.asset('assets/boot/grid-$frame.png',
                      fit: BoxFit.fill, gaplessPlayback: true),
                ),
                Positioned(
                  left: 0,
                  right: 0,
                  top: h * 140 / 720,
                  child: Opacity(
                    opacity: logoIn * pulse,
                    child: Center(
                      child: SizedBox(width: w * 0.62, child: Image.asset('assets/boot/logo.png')),
                    ),
                  ),
                ),
                Positioned(
                  left: streakX,
                  top: h * 640 / 720,
                  width: streakW,
                  child: Image.asset('assets/boot/streak.png', fit: BoxFit.fitWidth),
                ),
              ]);
            },
          );
        }),
      ),
    );
  }
}
