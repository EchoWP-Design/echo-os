// Neon-Farben und eine Kachel, die sich mit der Fernbedienung (Steuerkreuz +
// OK-Taste) genauso bedienen lässt wie per Touch.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

const neonBg = Color(0xFF07001A);
const neonPanel = Color(0xCC120230);
const neonCyan = Color(0xFF00F0FF);
const neonMagenta = Color(0xFFFF28C8);
const neonText = Color(0xFFE9E4FF);
const neonDim = Color(0xFF9A8FC4);

ThemeData neonTheme() => ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: neonBg,
      colorScheme: const ColorScheme.dark(
        primary: neonCyan,
        secondary: neonMagenta,
        surface: Color(0xFF120230),
      ),
      fontFamily: 'sans-serif',
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
        focusedBorder: OutlineInputBorder(borderSide: BorderSide(color: neonMagenta, width: 2)),
      ),
    );

/// Tasten, die eine Kachel auslösen: OK/Select der Fire-TV-Fernbedienung, Enter, Leertaste.
const activateShortcuts = <ShortcutActivator, Intent>{
  SingleActivator(LogicalKeyboardKey.select): ActivateIntent(),
  SingleActivator(LogicalKeyboardKey.enter): ActivateIntent(),
  SingleActivator(LogicalKeyboardKey.numpadEnter): ActivateIntent(),
  SingleActivator(LogicalKeyboardKey.gameButtonA): ActivateIntent(),
  SingleActivator(LogicalKeyboardKey.space): ActivateIntent(),
};

class NeonTile extends StatefulWidget {
  const NeonTile({
    super.key,
    required this.child,
    required this.onPressed,
    this.autofocus = false,
    this.glow = neonCyan,
  });

  final Widget child;
  final VoidCallback onPressed;
  final bool autofocus;
  final Color glow;

  @override
  State<NeonTile> createState() => _NeonTileState();
}

class _NeonTileState extends State<NeonTile> {
  bool _focused = false;

  @override
  Widget build(BuildContext context) {
    return FocusableActionDetector(
      autofocus: widget.autofocus,
      shortcuts: activateShortcuts,
      actions: <Type, Action<Intent>>{
        ActivateIntent: CallbackAction<ActivateIntent>(onInvoke: (_) {
          widget.onPressed();
          return null;
        }),
      },
      onFocusChange: (f) => setState(() => _focused = f),
      child: GestureDetector(
        onTap: widget.onPressed,
        child: AnimatedScale(
          scale: _focused ? 1.08 : 1.0,
          duration: const Duration(milliseconds: 140),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 140),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: _focused ? widget.glow : const Color(0x33FFFFFF),
                width: _focused ? 3 : 1,
              ),
              boxShadow: _focused
                  ? [BoxShadow(color: widget.glow, blurRadius: 18, spreadRadius: 1)]
                  : const [],
            ),
            child: ClipRRect(borderRadius: BorderRadius.circular(9), child: widget.child),
          ),
        ),
      ),
    );
  }
}

/// Neon-Überschrift „ECHO-OS“ in Kursiv mit Leuchten.
class NeonTitle extends StatelessWidget {
  const NeonTitle(this.text, {super.key, this.size = 40});

  final String text;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        fontSize: size,
        fontWeight: FontWeight.w900,
        fontStyle: FontStyle.italic,
        letterSpacing: 2,
        color: Colors.white,
        shadows: const [
          Shadow(color: neonCyan, blurRadius: 8),
          Shadow(color: neonCyan, blurRadius: 22),
        ],
      ),
    );
  }
}
