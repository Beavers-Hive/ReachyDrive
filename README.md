# Reachy Drive プロジェクト

Reachy Miniを助手席に座らせて、相棒として運転の体験をアップデートするプロジェクトです！

## フォルダ構成

- `app/`
    - Flutter製のiOSアプリ。Reachyの発言やGoogleMapのスマホ連携を行います。
- `server/`
    - Google Cloud Runにデプロイされるバックエンドサーバー。WebSocketを使用してアプリとロボット間の通信を仲介します。
- `src/`
    - システムのコアロジックを含むPythonソースコード。
    - `gemini_live_client.py`: Gemini Live APIとの連携。
    - `voicevox_client.py`: VOICEVOXによる音声合成。
    - `reachy_io_client.py`: Reachy Mini 本体の入出力制御。
- `reachy-mini-mcp/`
    - Reachy Mini 用の Model Context Protocol (MCP) サーバー
- `ble_led/`
    - BLE（Bluetooth Low Energy）を使用したLED制御のファームウェア
- `main.py`
    - ローカル環境でシステム全体を起動するためのメインエントリーポイント
- `.env`
    - 環境変数を管理する設定ファイルとして別途必要です