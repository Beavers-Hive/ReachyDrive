import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;

class WebSocketService {
  WebSocketChannel? _channel;
  final StreamController<Map<String, dynamic>> _messageController = StreamController.broadcast();
  
  // Default to localhost for emulator (android 10.0.2.2, ios localhost)
  // But for Cloud Run, we should use the deployed URL.
  // We will allow setting it or use a default.
  // For dev, if running on device, we need the computer's IP.
  // If running on simulator, localhost is fine.
  // Let's use a configurable URL.
  final String url;

  WebSocketService({required this.url});

  Stream<Map<String, dynamic>> get messages => _messageController.stream;

  void connect() {
    try {
      print("Connecting to WS: $url");
      _channel = WebSocketChannel.connect(Uri.parse(url));
      
      _channel!.stream.listen(
        (message) {
          print("WS Received: $message");
          try {
            final decoded = jsonDecode(message);
            _messageController.add(decoded);
          } catch (e) {
            print("Response was not JSON: $message");
          }
        },
        onError: (error) {
          print("WS Error: $error");
          _reconnect();
        },
        onDone: () {
          print("WS Closed");
          _reconnect();
        },
      );
    } catch (e) {
      print("Connection failed: $e");
      _reconnect();
    }
  }

  void _reconnect() {
    // Simple reconnect logic with delay
    Timer(const Duration(seconds: 3), () {
      print("Attempting reconnect...");
      connect();
    });
  }

  void sendMessage(Map<String, dynamic> data) {
    if (_channel != null) {
      _channel!.sink.add(jsonEncode(data));
    }
  }

  void close() {
    _channel?.sink.close(status.goingAway);
    _messageController.close();
  }
}
