import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';
import 'package:url_launcher/url_launcher.dart';
import 'services/websocket_service.dart';
import 'big_text_screen.dart';

class MonitorScreen extends StatefulWidget {
  const MonitorScreen({super.key});

  @override
  State<MonitorScreen> createState() => _MonitorScreenState();
}

class _MonitorScreenState extends State<MonitorScreen> {
  // Replace with your Cloud Run URL or local IP
  // e.g. 'wss://your-service-url.run.app/ws'
  // For Android Emulator: 'ws://10.0.2.2:8080/ws'
  // For iOS Simulator: 'ws://localhost:8080/ws'
  // For Physical Device: 'ws://YOUR_COMPUTER_IP:8080/ws'
  late final String _wsUrl;
  
  late WebSocketService _wsService;
  final List<Map<String, dynamic>> _messages = [];
  String _lastRobotMessage = "";
  final ScrollController _scrollController = ScrollController();
  final TextEditingController _urlController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _wsUrl = dotenv.get('WEBSOCKET_URL', fallback: 'ws://10.0.2.2:8080/ws');
    _urlController.text = _wsUrl;
    _startConnection();
  }

  void _startConnection() {
    _wsService = WebSocketService(url: _urlController.text);
    _wsService.connect();
    _wsService.messages.listen((data) {
      setState(() {
        _messages.add(data);
        if (data['type'] == 'text' && data['speaker'] == 'robot') {
          _lastRobotMessage = data['content'] ?? "";
        }
      });
      _scrollToBottom();
    });
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  void dispose() {
    _wsService.close();
    _scrollController.dispose();
    _urlController.dispose();
    super.dispose();
  }
  
  void _openSettings(BuildContext context) {
      showDialog(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text("Server Settings"),
          content: TextField(
            controller: _urlController,
            decoration: const InputDecoration(labelText: "WebSocket URL"),
          ),
          actions: [
            TextButton(
              onPressed: () {
                Navigator.pop(ctx);
                // Reconnect
                _wsService.close();
                _messages.clear(); // Optional: clear chat on reconnect
                _startConnection();
              },
              child: const Text("Connect"),
            )
          ],
        ),
      );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Reachy Live Monitor'),
        leading: IconButton(
          icon: const Icon(Icons.fullscreen),
          onPressed: () {
            if (_lastRobotMessage.isNotEmpty) {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (context) => BigTextScreen(text: _lastRobotMessage),
                ),
              );
            } else {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("まだ発話がありません")),
              );
            }
          },
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => _openSettings(context),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(16),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                return _buildMessageItem(msg);
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageItem(Map<String, dynamic> msg) {
    final type = msg['type'];
    
    if (type == 'text') {
      final isRobot = msg['speaker'] == 'robot';
      return Align(
        alignment: isRobot ? Alignment.centerLeft : Alignment.centerRight,
        child: Container(
          constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: isRobot 
                ? Theme.of(context).colorScheme.primaryContainer 
                : Theme.of(context).colorScheme.secondaryContainer,
            borderRadius: BorderRadius.only(
              topLeft: const Radius.circular(16),
              topRight: const Radius.circular(16),
              bottomLeft: isRobot ? Radius.zero : const Radius.circular(16),
              bottomRight: isRobot ? const Radius.circular(16) : Radius.zero,
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isRobot ? "Reachy" : "User",
                style: TextStyle(
                  fontSize: 10,
                  color: isRobot 
                    ? Theme.of(context).colorScheme.onPrimaryContainer.withOpacity(0.6)
                    : Theme.of(context).colorScheme.onSecondaryContainer.withOpacity(0.6),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                msg['content'] ?? "",
                style: TextStyle(
                  color: isRobot 
                    ? Theme.of(context).colorScheme.onPrimaryContainer
                    : Theme.of(context).colorScheme.onSecondaryContainer,
                ),
              ),
            ],
          ),
        ).animate().fade().scale(duration: 200.ms, alignment: isRobot ? Alignment.bottomLeft : Alignment.bottomRight),
      );
    } else if (type == 'location') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0),
        child: Card(
          elevation: 4,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.location_on, color: Colors.red),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        msg['name'] ?? "Unknown Location",
                        style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                if (msg['address'] != null) ...[
                   const SizedBox(height: 8),
                   Text(msg['address'], style: Theme.of(context).textTheme.bodyMedium),
                ],
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: () => _openMaps(msg),
                    icon: const Icon(Icons.map),
                    label: const Text("Google Mapsで開く"),
                  ),
                ),
              ],
            ),
          ),
        ).animate().slideY().fade(),
      );
    }
    return Container();
  }

  Future<void> _openMaps(Map<String, dynamic> msg) async {
    // Construct Google Maps URL
    // Try to use query if available, otherwise name + address
    final query = msg['query'] ?? "${msg['name']} ${msg['address']}";
    final encodedQuery = Uri.encodeComponent(query);
    final url = Uri.parse("https://www.google.com/maps/search/?api=1&query=$encodedQuery");
    
    try {
      if (await canLaunchUrl(url)) {
        await launchUrl(url, mode: LaunchMode.externalApplication);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text("地図を開けませんでした")),
        );
      }
    } catch (e) {
      print("Error launching maps: $e");
    }
  }
}
