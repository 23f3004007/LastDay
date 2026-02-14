import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:intl/intl.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:android_intent_plus/android_intent.dart';
import 'package:android_intent_plus/flag.dart';
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

import '../api_service.dart';
import '../models.dart';
import '../main.dart';

Future<void> _launchGmail(String emailId) async {
  final String nativeUrl = "googlegmail:///v1/account/me/thread/$emailId";
  final Uri webUrl = Uri.parse("https://mail.google.com/mail/u/0/#inbox/$emailId");
  try {
    final AndroidIntent intent = AndroidIntent(
      action: 'android.intent.action.VIEW',
      data: nativeUrl, 
      package: 'com.google.android.gm', 
      flags: <int>[Flag.FLAG_ACTIVITY_NEW_TASK],
    );
    await intent.launch();
  } catch (e) {
    if (await canLaunchUrl(webUrl)) {
      await launchUrl(webUrl, mode: LaunchMode.externalApplication);
    }
  }
}

String extractEmailAddress(String rawSender) {
  final RegExp regex = RegExp(r'<([^>]+)>');
  final match = regex.firstMatch(rawSender);
  return (match != null && match.groupCount >= 1) ? match.group(1)! : rawSender;
}

String getRelativeTime(DateTime date) {
  final now = DateTime.now();
  final difference = date.difference(now);

  if (difference.isNegative) return "OVERDUE";
  if (difference.inHours < 24 && date.day == now.day) {
    return "TODAY ${DateFormat('HH:mm').format(date)}";
  } else if (difference.inDays == 0 || (difference.inDays == 1 && date.day != now.day)) {
    return "TMRO ${DateFormat('HH:mm').format(date)}";
  } else if (difference.inDays < 7) {
    return "IN ${difference.inDays} DAYS";
  } else {
    return DateFormat('MMM dd').format(date).toUpperCase();
  }
}

Color getUrgencyColor(DateTime date) {
  final hoursLeft = date.difference(DateTime.now()).inHours;
  if (hoursLeft < 0) return Colors.grey.withOpacity(0.5); 
  if (hoursLeft < 24) return kDanger;
  if (hoursLeft < 72) return Colors.orangeAccent;
  return kAccent;
}

// --- HOME SCREEN ---
class HomeScreen extends StatefulWidget {
  final String accessToken;
  const HomeScreen({super.key, required this.accessToken});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _api = ApiService();
  List<Deadline> _deadlines = [];
  bool _isLoading = false;
  Timer? _syncTimer;

  // Local state
  List<String> _ignoredEmailIds = []; 
  List<String> _blockedSenders = [];
  Set<String> _importantEmailIds = {};

  @override
  void initState() {
    super.initState();
    _loadLocalState(); 
    
    // Auto-sync every 5 minutes
    _syncTimer = Timer.periodic(const Duration(minutes: 5), (timer) {
      if (mounted) _handleSync(isBackground: true); 
    });
  }

  @override
  void dispose() {
    _syncTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadLocalState() async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _ignoredEmailIds = prefs.getStringList('ignored_emails') ?? [];
      _blockedSenders = prefs.getStringList('blocked_senders') ?? [];
      _importantEmailIds = (prefs.getStringList('important_emails') ?? []).toSet();
    });
    _handleSync(isBackground: false); 
  }

  Future<void> _handleSync({bool isBackground = false}) async {
    if (!isBackground) setState(() => _isLoading = true);
    
    try {
      final rawDeadlines = await _api.syncEmails(widget.accessToken);
      
      // Apply Local Importance
      for (var item in rawDeadlines) {
        if (_importantEmailIds.contains(item.emailId)) item.isImportant = true;
      }

      // Apply Filters
      final filteredDeadlines = rawDeadlines.where((item) {
        final isIgnoredId = _ignoredEmailIds.contains(item.emailId);
        final pureSender = extractEmailAddress(item.sender);
        final isBlocked = _blockedSenders.contains(pureSender);
        return !isIgnoredId && !isBlocked; 
      }).toList();

      // Sort
      filteredDeadlines.sort((a, b) {
        if (a.isImportant && !b.isImportant) return -1;
        if (!a.isImportant && b.isImportant) return 1;
        int comparison = a.deadlineTime.compareTo(b.deadlineTime);
        return comparison == 0 ? a.subject.compareTo(b.subject) : comparison;
      });

      if (mounted) setState(() => _deadlines = filteredDeadlines);

    } catch (e) {
      if (mounted && !isBackground) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Sync Error: $e")));
      }
    } finally {
      if (mounted && !isBackground) setState(() => _isLoading = false);
    }
  }

  // --- ACTIONS ---
  Future<void> _dismissItem(int index, Deadline item, DismissDirection direction) async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      _deadlines.removeAt(index);
      _ignoredEmailIds.add(item.emailId);
    });
    await prefs.setStringList('ignored_emails', _ignoredEmailIds);

    // Left Swipe (Red) = Spam/Not Important
    // Right Swipe (Green) = Done
    bool isSpam = (direction == DismissDirection.endToStart);
    
    // Call API with subject
    _api.sendFeedback(item.emailId, item.subject, item.snippet, isSpam);
    
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(isSpam ? "Marked Not Important 🧠" : "Marked Done ✅"),
        duration: const Duration(seconds: 1),
      ));
    }
  }

  Future<void> _toggleImportance(Deadline item) async {
    final prefs = await SharedPreferences.getInstance();
    setState(() {
      item.isImportant = !item.isImportant;
      if (item.isImportant) _importantEmailIds.add(item.emailId);
      else _importantEmailIds.remove(item.emailId);
      
      _deadlines.sort((a, b) {
         if (a.isImportant && !b.isImportant) return -1;
         if (!a.isImportant && b.isImportant) return 1;
         return a.deadlineTime.compareTo(b.deadlineTime);
      });
    });
    await prefs.setStringList('important_emails', _importantEmailIds.toList());
    Navigator.pop(context);
  }

  Future<void> _blockSender(String rawSender) async {
    final prefs = await SharedPreferences.getInstance();
    final pureEmail = extractEmailAddress(rawSender);
    setState(() {
      _blockedSenders.add(pureEmail);
      _deadlines.removeWhere((item) => extractEmailAddress(item.sender) == pureEmail);
    });
    await prefs.setStringList('blocked_senders', _blockedSenders);
    Navigator.pop(context);
  }

  void _showOptionsModal(Deadline item) {
    showModalBottomSheet(
      context: context,
      backgroundColor: kSurface,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(width: 40, height: 4, decoration: BoxDecoration(color: Colors.grey[700], borderRadius: BorderRadius.circular(2))),
              const SizedBox(height: 16),
              ListTile(
                leading: Icon(Icons.star, color: item.isImportant ? Colors.grey : kImportant),
                title: Text(item.isImportant ? "Unmark as Important" : "Mark as Important", style: const TextStyle(color: kTextWhite)),
                onTap: () => _toggleImportance(item),
              ),
              ListTile(
                leading: const Icon(Icons.block, color: kDanger),
                title: Text("Stop reminders from this sender", style: const TextStyle(color: kDanger)),
                subtitle: Text(extractEmailAddress(item.sender), style: TextStyle(color: Colors.grey[500], fontSize: 12)),
                onTap: () => _blockSender(item.sender),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _logout() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.clear();
    _syncTimer?.cancel();
    if (mounted) Navigator.of(context).pushNamedAndRemoveUntil('/login', (route) => false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: kBackground,
      appBar: AppBar(
        title: const Text("LASTDAY"), centerTitle: true,
        actions: [
          IconButton(icon: const Icon(Icons.sync, color: kAccent), onPressed: () => _handleSync(isBackground: false)),
          IconButton(icon: const Icon(Icons.logout, color: Colors.grey), onPressed: _logout),
        ],
      ),
      body: _isLoading && _deadlines.isEmpty
          ? const Center(child: CircularProgressIndicator(color: kAccent))
          : _deadlines.isEmpty
              ? const Center(child: Text("NO TARGETS DETECTED", style: TextStyle(color: Colors.grey, letterSpacing: 2)))
              : ListView.builder(
                  itemCount: _deadlines.length,
                  itemBuilder: (context, index) {
                    final item = _deadlines[index];
                    return Dismissible(
                      key: Key(item.emailId), 
                      background: Container(color: Colors.green.withOpacity(0.8), alignment: Alignment.centerLeft, padding: const EdgeInsets.only(left: 20), child: const Icon(Icons.check_circle, color: Colors.white)),
                      secondaryBackground: Container(color: kDanger.withOpacity(0.8), alignment: Alignment.centerRight, padding: const EdgeInsets.only(right: 20), child: const Icon(Icons.delete_forever, color: Colors.white)),
                      onDismissed: (direction) => _dismissItem(index, item, direction),
                      child: DeadlineCard(
                        item: item,
                        onTap: () => _launchGmail(item.emailId),
                        onLongPress: () => _showOptionsModal(item),
                      ),
                    );
                  },
                ),
    );
  }
}

// --- DEADLINE CARD WIDGET ---
class DeadlineCard extends StatelessWidget {
  final Deadline item;
  final VoidCallback onTap;
  final VoidCallback onLongPress;

  const DeadlineCard({
    super.key, 
    required this.item, 
    required this.onTap, 
    required this.onLongPress
  });

  @override
  Widget build(BuildContext context) {
    final stripColor = item.isImportant ? kImportant : getUrgencyColor(item.deadlineTime);
    final relativeTime = getRelativeTime(item.deadlineTime);
    final displayName = item.sender.split('<')[0].trim();
    final String specificDateTime = DateFormat('MMM dd • h:mm a').format(item.deadlineTime);

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: kSurface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: item.isImportant ? kImportant.withOpacity(0.5) : Colors.white.withOpacity(0.05)
        ),
        boxShadow: [
           BoxShadow(color: Colors.black.withOpacity(0.3), blurRadius: 10, offset: const Offset(0, 4)),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(12),
          onTap: onTap,
          onLongPress: onLongPress,
          child: IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Container(
                  width: 4,
                  decoration: BoxDecoration(
                    color: stripColor,
                    borderRadius: const BorderRadius.only(topLeft: Radius.circular(12), bottomLeft: Radius.circular(12)),
                    boxShadow: [BoxShadow(color: stripColor.withOpacity(0.4), blurRadius: 8)],
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Text(
                                item.subject,
                                maxLines: 2,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                  color: item.isImportant ? kImportant : kTextWhite,
                                  height: 1.2,
                                ),
                              ),
                            ),
                            const SizedBox(width: 8),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: stripColor.withOpacity(0.1),
                                borderRadius: BorderRadius.circular(6),
                                border: Border.all(color: stripColor.withOpacity(0.3)),
                              ),
                              child: Text(
                                relativeTime,
                                style: TextStyle(color: stripColor, fontWeight: FontWeight.bold, fontSize: 10),
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Row(
                          children: [
                            Icon(Icons.person_outline, size: 12, color: Colors.grey[500]),
                            const SizedBox(width: 4),
                            Flexible(
                              child: Text(
                                displayName, 
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                              ),
                            ),
                            const Spacer(),
                            Icon(Icons.access_time, size: 12, color: kAccent),
                            const SizedBox(width: 4),
                            Text(
                              specificDateTime, 
                              style: const TextStyle(
                                fontSize: 12, 
                                color: kTextWhite, 
                                fontWeight: FontWeight.w600
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          item.snippet,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: 12, 
                            color: Colors.grey[600], 
                            height: 1.4, 
                            fontFamily: 'RobotoMono'
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}