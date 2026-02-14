"""
Reachy Mini Realtime BPM Headbang Program
音楽からBPMをリアルタイムで検出し、そのリズムに合わせてヘッドバンします
BLE経由でLEDも同期制御します
"""

import pyaudio
import numpy as np
import librosa
import time
import threading
import asyncio
from collections import deque
from reachy_mini import ReachyMini
from reachy_mini.utils import create_head_pose
from bleak import BleakClient, BleakScanner

# --- 設定 ---
RATE = 44100
CHUNK_SIZE = 2048  # 処理単位
BPM_LISTEN_DURATION = 5  # BPM推定に使う最低リスニング時間（秒）
BPM_HISTORY_SIZE = 5  # BPM履歴のサイズ（平滑化用）
SILENCE_THRESHOLD = 0.01  # 無音判定の閾値（RMS）
SILENCE_DURATION = 2.0  # 無音と判定する継続時間（秒）

# --- BLE設定 ---
BLE_SERVICE_UUID = "4fafc201-1sb5-45ae-3fcc-c5c9c331914b"
BLE_CHARACTERISTIC_UUID = "ceb5483e-36e1-2688-b7f5-ea07361d26a8"


class RealtimeBPMDetector:
    """リアルタイムでBPMを検出するクラス"""
    
    # 状態定義
    STATE_WAITING = "waiting"      # 音楽を待っている
    STATE_LISTENING = "listening"  # 音楽を聴いてBPM推定中
    STATE_READY = "ready"          # BPM推定完了、ダンスOK
    STATE_SILENT = "silent"        # 無音検出、ダンス停止
    
    def __init__(self):
        self.current_bpm = None  # BPM未検出
        self.lock = threading.Lock()
        self.running = False
        self.bpm_history = deque(maxlen=BPM_HISTORY_SIZE)
        self.thread = None
        self.state = self.STATE_WAITING
        
        # PyAudio settings
        self.p = None
        self.stream = None
        
    def get_bpm(self):
        """現在のBPMを取得（スレッドセーフ）"""
        with self.lock:
            return self.current_bpm
    
    def get_state(self):
        """現在の状態を取得（スレッドセーフ）"""
        with self.lock:
            return self.state
    
    def can_dance(self):
        """ダンスできる状態か（スレッドセーフ）"""
        with self.lock:
            return self.state == self.STATE_READY and self.current_bpm is not None
    
    def _detection_loop(self):
        """バックグラウンドで動作するBPM検出ループ"""
        try:
            # PyAudio設定
            self.p = pyaudio.PyAudio()
            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=1,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK_SIZE
            )
            
            audio_buffer = []
            buffer_size = RATE * BPM_LISTEN_DURATION
            music_start_time = None  # 音楽が始まった時刻
            silence_start_time = None  # 無音が始まった時刻
            
            print("🎧 リアルタイムBPM検出を開始しました")
            
            while self.running:
                try:
                    # マイクからデータ読み込み
                    data = self.stream.read(CHUNK_SIZE, exception_on_overflow=False)
                    samples = np.frombuffer(data, dtype=np.float32)
                    
                    # 音量を計算（RMS）
                    rms = np.sqrt(np.mean(samples**2))
                    is_sound = rms >= SILENCE_THRESHOLD
                    current_time = time.time()
                    
                    with self.lock:
                        current_state = self.state
                    
                    if current_state == self.STATE_WAITING:
                        # 音楽を待っている状態
                        if is_sound:
                            # 音楽が始まった → リスニング状態へ
                            with self.lock:
                                self.state = self.STATE_LISTENING
                            music_start_time = current_time
                            audio_buffer = list(samples)
                            silence_start_time = None
                            print("🎵 音楽を検出 - BPM推定を開始します...")
                    
                    elif current_state == self.STATE_LISTENING:
                        # 音楽を聴いてBPM推定中
                        if is_sound:
                            audio_buffer.extend(samples)
                            silence_start_time = None
                            
                            # 十分な音声データが溜まったらBPM推定
                            listen_elapsed = current_time - music_start_time if music_start_time else 0
                            if listen_elapsed >= BPM_LISTEN_DURATION and len(audio_buffer) >= buffer_size:
                                audio_array = np.array(audio_buffer[-buffer_size:])
                                try:
                                    tempo, beats = librosa.beat.beat_track(y=audio_array, sr=RATE)
                                    if isinstance(tempo, np.ndarray):
                                        tempo = tempo.item()
                                    
                                    if 40 < tempo < 250:
                                        self.bpm_history.append(tempo)
                                        estimated_bpm = np.median(list(self.bpm_history))
                                        
                                        with self.lock:
                                            self.current_bpm = estimated_bpm
                                            self.state = self.STATE_READY
                                        print(f"✅ BPM推定完了: {estimated_bpm:.1f} BPM - ダンス開始！")
                                except Exception:
                                    pass
                        else:
                            # リスニング中に無音 → 待機に戻る
                            if silence_start_time is None:
                                silence_start_time = current_time
                            elif current_time - silence_start_time >= SILENCE_DURATION:
                                with self.lock:
                                    self.state = self.STATE_WAITING
                                audio_buffer = []
                                music_start_time = None
                                silence_start_time = None
                                print("🔇 音楽が途切れました - 再度音楽を待機中...")
                    
                    elif current_state == self.STATE_READY:
                        # ダンス中 - 無音を検出したら停止
                        if is_sound:
                            audio_buffer.extend(samples)
                            # バッファサイズを制限
                            if len(audio_buffer) > buffer_size * 2:
                                audio_buffer = audio_buffer[-buffer_size:]
                            silence_start_time = None
                        else:
                            if silence_start_time is None:
                                silence_start_time = current_time
                            elif current_time - silence_start_time >= SILENCE_DURATION:
                                # 無音状態に移行
                                with self.lock:
                                    self.state = self.STATE_SILENT
                                silence_start_time = None
                                print("🔇 無音を検出 - ダンス停止")
                    
                    elif current_state == self.STATE_SILENT:
                        # 無音状態 - 音楽が再開したらリスニング
                        if is_sound:
                            with self.lock:
                                self.state = self.STATE_LISTENING
                                self.bpm_history.clear()  # 新しい曲なのでBPM履歴をリセット
                            music_start_time = current_time
                            audio_buffer = list(samples)
                            silence_start_time = None
                            print("🎵 音楽を検出 - BPM推定を開始します...")
                
                except Exception:
                    pass
        
        finally:
            if self.stream is not None:
                self.stream.stop_stream()
                self.stream.close()
            if self.p is not None:
                self.p.terminate()
    
    def start(self):
        """BPM検出スレッドを開始"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._detection_loop, daemon=True)
            self.thread.start()
    
    def stop(self):
        """BPM検出スレッドを停止"""
        self.running = False
        if self.thread is not None:
            self.thread.join(timeout=2.0)


class BLELedController:
    """BLE経由でLEDを制御するクラス"""
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.loop = None
        self.thread = None
        self._command_queue = []
        self._queue_lock = threading.Lock()
    
    def start(self):
        """BLE接続をバックグラウンドスレッドで開始"""
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def _run_loop(self):
        """asyncioイベントループを実行"""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self._ble_main())
    
    async def _ble_main(self):
        """BLE接続とコマンド送信のメインループ"""
        print("🔵 BLEデバイス 'LED' をスキャン中...")
        
        try:
            # デバイス名「LED」で検索
            device = await BleakScanner.find_device_by_name(
                "LED",
                timeout=10.0
            )
            
            if device is None:
                print("⚠️ BLEデバイス 'LED' が見つかりません。LED制御なしで続行します。")
                return
            
            print(f"✓ BLEデバイス発見: {device.name} ({device.address})")
            
            async with BleakClient(device) as client:
                self.client = client
                self.connected = True
                print("✓ BLE接続成功！")
                
                # コマンド送信ループ
                while self.connected:
                    cmd = None
                    with self._queue_lock:
                        if self._command_queue:
                            cmd = self._command_queue.pop(0)
                    
                    if cmd:
                        try:
                            await client.write_gatt_char(
                                BLE_CHARACTERISTIC_UUID,
                                cmd.encode("utf-8")
                            )
                        except Exception as e:
                            print(f"⚠️ BLE送信エラー: {e}")
                    else:
                        await asyncio.sleep(0.01)
        
        except Exception as e:
            print(f"⚠️ BLE接続エラー: {e}")
            print("LED制御なしで続行します。")
    
    def send(self, command):
        """コマンドをキューに追加（スレッドセーフ）"""
        with self._queue_lock:
            self._command_queue.clear()  # 古いコマンドを捨てて最新のみ
            self._command_queue.append(command)
    
    def rainbow(self):
        """虹色に点灯"""
        self.send("rainbow")
    
    def off(self):
        """消灯"""
        self.send("none")
    
    def stop(self):
        """BLE接続を停止"""
        if self.connected:
            self.send("none")  # 消灯してから切断
            time.sleep(0.1)
        self.connected = False


def headbang_realtime(mini, bpm_detector, led_controller, duration=3000):
    """
    リアルタイムBPMに合わせてヘッドバン、アンテナ、ボディを動かす
    """
    print(f"\n🤘 音楽に合わせてヘッドバン！")
    print(f"   音楽を流してください。BPM推定後にダンスを開始します (Ctrl+Cで停止)")
    
    start_time = time.time()
    beat_count = 0
    
    try:
        while (time.time() - start_time) < duration:
            # ダンスできる状態かチェック
            if not bpm_detector.can_dance():
                time.sleep(0.1)
                continue
            
            # 現在のBPMを取得
            current_bpm = bpm_detector.get_bpm()
            
            # BPMから動作時間を計算
            beat_duration = 60.0 / current_bpm
            move_duration = beat_duration / 2.0
            
            # ビートの左右を交互に切り替え
            is_left = (beat_count % 2 == 0)
            
            # ヘッドバン: 下に振る (pitch down) - 小さめの動き
            head_down = create_head_pose(pitch=12, degrees=True)
            # アンテナ: 同じ方向に動かす (ラジアン単位)
            antenna_angle = np.deg2rad(30)
            antennas_down = [antenna_angle, antenna_angle] if is_left else [-antenna_angle, -antenna_angle]
            # ボディ: 左右に振る (ラジアン単位)
            body_yaw_angle = np.deg2rad(15) if is_left else np.deg2rad(-15)
            
            mini.set_target(head=head_down, antennas=antennas_down, body_yaw=body_yaw_angle)
            led_controller.rainbow()  # ビートに合わせてLED点灯
            time.sleep(move_duration)
            
            # ヘッドバン: 上に戻す (pitch up) - 小さめの動き
            head_up = create_head_pose(pitch=-8, degrees=True)
            # アンテナ: 逆方向に動かす
            antennas_up = [-antenna_angle, -antenna_angle] if is_left else [antenna_angle, antenna_angle]
            # ボディ: 逆方向に振る
            body_yaw_up = np.deg2rad(-15) if is_left else np.deg2rad(15)
            
            mini.set_target(head=head_up, antennas=antennas_up, body_yaw=body_yaw_up)
            led_controller.off()  # LED消灯
            time.sleep(move_duration)
            
            beat_count += 1
            
    except KeyboardInterrupt:
        print("\n\nヘッドバンを停止しました")
    
    # ニュートラル位置に戻す
    print("ニュートラル位置に戻します...")
    led_controller.off()
    mini.set_target(head=create_head_pose(), antennas=[0.0, 0.0], body_yaw=0.0)
    time.sleep(1)


def main():
    """メイン処理"""
    print("=" * 50)
    print("🎸 Reachy Mini Realtime BPM Headbang 🎸")
    print("=" * 50)
    
    bpm_detector = RealtimeBPMDetector()
    led_controller = BLELedController()
    
    try:
        print("\n[ステップ 1] Reachy Mini に接続")
        
        with ReachyMini(media_backend="no_media") as mini:
            print("✓ 接続成功！")
            
            print("\n[ステップ 2] BLE LED接続")
            led_controller.start()
            time.sleep(3)  # BLE接続待ち
            
            print("\n[ステップ 3] リアルタイムBPM検出を開始")
            bpm_detector.start()
            
            print("\n[ステップ 4] 音楽を待機中...")
            headbang_realtime(mini, bpm_detector, led_controller, duration=3000)
            
            print("\n✓ プログラム終了")
            
    except Exception as e:
        print(f"❌ エラー: {e}")
        print("Reachy Mini daemon が起動しているか確認してください")
    
    finally:
        print("停止中...")
        led_controller.stop()
        bpm_detector.stop()


if __name__ == "__main__":
    main()
