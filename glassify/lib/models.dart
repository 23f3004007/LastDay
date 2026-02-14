class Deadline {
  final String emailId;
  final String subject;
  final String sender; // <--- New field
  final DateTime deadlineTime;
  final String snippet;
  bool isImportant; // Local UI state

  Deadline({
    required this.emailId,
    required this.subject,
    required this.sender,
    required this.deadlineTime,
    required this.snippet,
    this.isImportant = false,
  });

  factory Deadline.fromJson(Map<String, dynamic> json) {
    return Deadline(
      emailId: json['email_id'],
      subject: json['subject'] ?? "No Subject",
      // Ensure your backend sends this key correctly
      sender: json['sender'] ?? "Unknown", 
      deadlineTime: DateTime.parse(json['deadline_time']),
      snippet: json['snippet'] ?? "",
    );
  }
}