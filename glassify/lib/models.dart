class Deadline {
  final String emailId;
  final String subject;
  final String sender;
  final DateTime deadlineTime;
  final String snippet;
  bool isImportant;

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
      sender: json['sender'] ?? "Unknown", 
      deadlineTime: DateTime.parse(json['deadline_time']),
      snippet: json['snippet'] ?? "",
    );
  }
}