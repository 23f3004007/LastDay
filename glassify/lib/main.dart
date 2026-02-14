import 'dart:async';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;
import 'package:url_launcher/url_launcher.dart';
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';

import 'api_service.dart';
import 'models.dart';
import 'secrets.dart';
import 'screens/home_screen.dart';

// --- GLOBAL THEME ---
const Color kBackground = Color(0xFF0B0F19);
const Color kSurface = Color(0xFF151A25);
const Color kAccent = Color(0xFF00F0FF);
const Color kDanger = Color(0xFFFF2A6D);
const Color kImportant = Color(0xFFFFD700); 
const Color kTextWhite = Color(0xFFE0E6ED);

final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin =
    FlutterLocalNotificationsPlugin();

// --- ENTRY POINT ---
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  try {
    tz.initializeTimeZones();
    const AndroidInitializationSettings initializationSettingsAndroid =
        AndroidInitializationSettings('@mipmap/launcher_icon');
    final InitializationSettings initializationSettings =
        InitializationSettings(android: initializationSettingsAndroid);
    await flutterLocalNotificationsPlugin.initialize(initializationSettings);
  } catch (e) {
    print("Startup Error: $e");
  }
  runApp(const LastDayApp());
}

// --- GLOBAL UTILS (Used by Home Screen) ---
Future<void> _launchGmail(String emailId) async {
  final String nativeUrl = "googlegmail:///v1/account/me/thread/$emailId";
  final Uri webUrl = Uri.parse("https://mail.google.com/mail/u/0/#inbox/$emailId");
  try {
    final AndroidIntent intent = AndroidIntent(
      action: 'android.intent.action.VIEW',
      data: nativeUrl, package: 'com.google.android.gm', flags: <int>[Flag.FLAG_ACTIVITY_NEW_TASK],
    );
    await intent.launch();
  } catch (e) {
    if (await canLaunchUrl(webUrl)) await launchUrl(webUrl, mode: LaunchMode.externalApplication);
  }
}

String extractEmailAddress(String rawSender) {
  final RegExp regex = RegExp(r'<([^>]+)>');
  final match = regex.firstMatch(rawSender);
  return (match != null && match.groupCount >= 1) ? match.group(1)! : rawSender;
}

// --- MAIN APP ---
class LastDayApp extends StatelessWidget {
  const LastDayApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'LastDay',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: kBackground,
        primaryColor: kAccent,
        appBarTheme: const AppBarTheme(backgroundColor: kBackground, elevation: 0),
        colorScheme: const ColorScheme.dark(primary: kAccent, secondary: kDanger, surface: kSurface),
      ),
      // Define routes to make navigation easier
      routes: {
        '/': (context) => const SplashScreen(),
        '/login': (context) => const LoginScreen(),
      },
    );
  }
}

// --- SPLASH SCREEN ---
class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});
  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _checkLogin();
  }

  Future<void> _checkLogin() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    await Future.delayed(const Duration(seconds: 1)); // Short delay for branding
    if (token != null) {
      if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => HomeScreen(accessToken: token)));
    } else {
      if (mounted) Navigator.pushReplacementNamed(context, '/login');
    }
  }

  @override
  Widget build(BuildContext context) {
    return const Scaffold(backgroundColor: kBackground, body: Center(child: CircularProgressIndicator(color: kAccent)));
  }
}

// --- NEW LOGIN SCREEN ---
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final String _serverClientId = kGoogleClientId;
  late GoogleSignIn _googleSignIn;
  final ApiService _api = ApiService();
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _googleSignIn = GoogleSignIn(
      serverClientId: _serverClientId, 
      scopes: ['email', 'https://www.googleapis.com/auth/gmail.readonly'],
    );
  }

  Future<void> _handleSignIn() async {
    setState(() => _isLoading = true);
    try {
      if (await _googleSignIn.isSignedIn()) {
         try { await _googleSignIn.disconnect(); } catch (_) {}
      }
      final GoogleSignInAccount? account = await _googleSignIn.signIn();
      if (account != null && account.serverAuthCode != null) {
        final token = await _api.exchangeCodeForToken(account.serverAuthCode!);
        if (token != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString('access_token', token);
          if (mounted) Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => HomeScreen(accessToken: token)));
        }
      }
    } catch (error) {
      if(mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Login Failed: $error")));
    } finally {
      if(mounted) setState(() => _isLoading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBackground,
      // ✅ FIX: Use SizedBox.expand to force full width/height
      body: SizedBox.expand( 
        child: Padding(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.center, // ✅ Force horizontal center
            children: [
              const Spacer(),
              // --- YOUR ICON ---
              Container(
                width: 120, height: 120,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: [BoxShadow(color: kAccent.withOpacity(0.2), blurRadius: 20)],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  // Ensure this is your PNG asset
                  child: Image.asset('assets/icon.png', errorBuilder: (c,e,s) => const Icon(Icons.error, color: Colors.red)), 
                ),
              ),
              const SizedBox(height: 32),
              const Text(
                "LastDay",
                style: TextStyle(fontSize: 36, fontWeight: FontWeight.bold, color: Colors.white, letterSpacing: 1.5),
              ),
              const SizedBox(height: 16),
              const Text(
                "Never miss a deadline again.\nAI-powered tracking for your Gmail.",
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, color: Colors.grey, height: 1.5),
              ),
              const Spacer(),
              
              // --- LOGIN BUTTON / LOADER ---
              // We wrap this in a container of fixed height so the layout doesn't jump vertically either
              SizedBox(
                height: 50, 
                width: double.infinity, // ✅ Force full width
                child: _isLoading
                  ? const Center(child: CircularProgressIndicator(color: kAccent))
                  : ElevatedButton.icon(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: Colors.black,
                        padding: EdgeInsets.zero, // Remove padding to let SizedBox control size
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      // ✅ Use the PNG logo here
                      icon: Image.network(
                        'https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/Google_%22G%22_Logo.svg/512px-Google_%22G%22_Logo.svg.png', 
                        height: 24
                      ),
                      label: const Text("Log in with Google", style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                      onPressed: _handleSignIn,
                    ),
              ),
              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}
