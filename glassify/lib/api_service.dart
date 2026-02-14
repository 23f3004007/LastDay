import 'dart:convert';
import 'package:http/http.dart' as http;
import 'models.dart';

class ApiService {
  // Use 10.0.2.2 for Android Emulator to access localhost
  // If using a physical device, use your PC's local IP (e.g., 192.168.1.X)
  // FOR USB CONNECTION (ADB REVERSE)
  static const String baseUrl = "https://lastday-backend.onrender.com"; 

  // Endpoint: /auth/exchange
  Future<String?> exchangeCodeForToken(String serverAuthCode) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/auth/exchange'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'code': serverAuthCode}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['access_token']; // Extract token from Google response
      } else {
        print("Auth Exchange Failed: ${response.body}");
        return null;
      }
    } catch (e) {
      print("Error connecting to backend: $e");
      return null;
    }
  }

  // Endpoint: /sync
  Future<List<Deadline>> syncEmails(String accessToken) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/sync'),
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer $accessToken',
        },
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final List<dynamic> deadlinesJson = data['deadlines'];
        return deadlinesJson.map((json) => Deadline.fromJson(json)).toList();
      } else {
        throw Exception("Sync failed: ${response.body}");
      }
    } catch (e) {
      throw Exception("Error syncing: $e");
    }
  }
  Future<void> sendFeedback(String emailId, String subject, String snippet, bool isSpam) async {
    final url = Uri.parse("$baseUrl/feedback");
    
    try {
      final response = await http.post(
        url,
        headers: await _getHeaders(),
        body: jsonEncode({
          "email_id": emailId,
          "subject": subject, // <--- Add this
          "snippet": snippet,
          "is_spam": isSpam,
        }),
      );

      if (response.statusCode != 200) {
        print("Feedback failed: ${response.body}");
      }
    } catch (e) {
      print("Error sending feedback: $e");
    }
  }
  Future<Map<String, String>> _getHeaders() async {
    return {
      "Content-Type": "application/json",
      "Accept": "application/json",
    };
  }
}