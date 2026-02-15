# Reachy Drive プロジェクト
Reachy Miniを助手席に座らせて、相棒として運転の体験をアップデートするプロジェクトです！
第4回 AI Agent Hackathon with Google Cloudへの応募作品になります。 

![IMG_4056](https://github.com/user-attachments/assets/79d591d1-1fac-4877-bffa-18a334fb7fba)


動作の様子(YouTube動画)
https://youtu.be/EeeBkT2Rk1s

## 審査への申し送り事項
ハードウェアを用いたプロジェクトかつ、iOSアプリもロボットがないと動作しないもののためWebへのデプロイはできません。ご了承くださいませ。

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
