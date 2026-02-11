from reachy_mini import ReachyMini
import numpy as np
import cv2
import time
import sounddevice as sd
import queue
import sys
import traceback

class ReachyIOClient:
    def __init__(self):
        self.mini = None
        self.use_fallback = False
        
        try:
            print("Attempting to connect to Reachy Mini SDK...")
            # Try connecting. If camera fails, it raises Exception
            self.mini = ReachyMini()
            print("Connected to Reachy Mini SDK")
        except Exception as e:
            print(f"Failed to connect to Reachy Mini SDK: {e}")
            print("Switching to AUDIO FALLBACK mode (using system default/ReSpeaker).")
            self.use_fallback = True
            
            # List devices to help debugging
            print("Available Audio Devices:")
            print(sd.query_devices())

    def _get_device_index(self, name_keywords):
        """Helper to find device index by name"""
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                # Check for Reachy specific names (UAC-2, ReSpeaker, etc.)
                # Reachy Mini Speaker often shows as "UAC-2" or similar USB Audio
                dev_name = dev['name']
                for keyword in name_keywords:
                    if keyword in dev_name:
                         return i
        except Exception:
            pass
        return None

    async def audio_input_generator(self, sample_rate: int = 16000, chunk_size: int = 512):
        """
        Async generator that yields audio chunks from the microphone.
        """
        import sounddevice as sd
        import asyncio
        
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time, status):
            if status:
                print(status, file=sys.stderr)
            loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

        target_device = self._get_device_index(["ReSpeaker", "UAC-2", "USB Audio", "Reachy"])
        
        # We'll run the stream in a context manager
        stream = sd.InputStream(
            samplerate=sample_rate,
            channels=1,
            dtype='int16',
            device=target_device,
            callback=callback,
            blocksize=chunk_size
        )
        
        with stream:
            while True:
                chunk = await queue.get()
                yield chunk

    def start_output_stream(self, sample_rate: int = 24000):
        """
        Initialize the output stream for playback.
        Uses a background thread to write to the stream to avoid blocking the asyncio loop.
        """
        if hasattr(self, 'output_stream') and self.output_stream.active:
             return

        import threading
        self.output_queue = queue.Queue()
        self.output_device = self._get_device_index(["UAC-2", "ReSpeaker", "USB Audio", "Reachy"])
        self.output_running = True
        
        def playback_thread():
            print("Audio Playback Thread Started")
            try:
                # Open stream in blocking mode in this thread
                with sd.OutputStream(
                    samplerate=sample_rate,
                    channels=1,
                    dtype='int16',
                    device=self.output_device
                ) as stream:
                    while self.output_running:
                        try:
                            # Get data with timeout to allow checking running flag
                            data_bytes = self.output_queue.get(timeout=0.1)
                            # Convert to numpy
                            data = np.frombuffer(data_bytes, dtype=np.int16)
                            stream.write(data)
                        except queue.Empty:
                            continue
                        except Exception as e:
                            print(f"Playback error: {e}")
            except Exception as e:
                print(f"Stream error: {e}")
            print("Audio Playback Thread Stopped")

        self.playback_thread = threading.Thread(target=playback_thread, daemon=True)
        self.playback_thread.start()
        self.output_stream = self.playback_thread # Mock object to signify active

    def play_stream_chunk(self, chunk: bytes):
        """
        Queue audio chunk for playback (Non-blocking).
        """
        if not hasattr(self, 'output_stream'):
            self.start_output_stream()
            
        # Just put in queue
        self.output_queue.put(chunk)

    def close(self):
        self.output_running = False
        if hasattr(self, 'playback_thread'):
            self.playback_thread.join(timeout=1.0)

    async def play_audio_async(self, audio_data: bytes, sample_rate: int = 24000):
        """
        Play raw audio data asynchronously (non-blocking for event loop).
        """
        try:
            import io
            import soundfile as sf
            import asyncio
            
            data, fs = sf.read(io.BytesIO(audio_data))
            
            # Keywords: "UAC-2", "Reachy", "USB Audio" - strictly output
            target_device = self._get_device_index(["UAC-2", "ReSpeaker", "USB Audio", "Reachy"])
            
            if target_device is not None:
                sd.play(data, fs, device=target_device)
            else:
                sd.play(data, fs)
            
            # Calculate duration and wait asynchronously
            # len(data) is num_frames * channels. data.shape[0] is num_frames.
            duration = data.shape[0] / fs
            await asyncio.sleep(duration + 0.5) # Add small buffer
            sd.stop()
                
        except Exception as e:
            print(f"Error playing audio: {e}")

    def play_audio(self, audio_data: bytes, sample_rate: int = 24000):
        """
        Play raw audio data.
        """
        try:
            import io
            import soundfile as sf
            
            data, fs = sf.read(io.BytesIO(audio_data))
            
            # Try to find Reachy Speaker
            # Keywords: "UAC-2", "Reachy", "USB Audio" - strictly output
            # User said "speaker from computer", we want "reachy"
            # Often "UAC-2" or "Seeed" for ReSpeaker (which has output too)
            # Let's try to find a USB output device if Reachy SDK failed
            # Keywords: "UAC-2", "Reachy", "USB Audio" - strictly output
            target_device = self._get_device_index(["UAC-2", "ReSpeaker", "USB Audio", "Reachy"])
            
            if target_device is not None:
                sd.play(data, fs, device=target_device)
            else:
                sd.play(data, fs)
            sd.wait()
                
        except Exception as e:
            print(f"Error playing audio: {e}")

    def record_audio(self, max_duration: float = 10.0, silence_threshold: float = 0.01, silence_duration: float = 1.0, sample_rate: int = 16000) -> bytes:
        """
        Record audio from microphone with VAD (Voice Activity Detection).
        Stops recording when silence is detected for `silence_duration` seconds,
        or when `max_duration` is reached.
        """
        try:
            print(f"Listening... (Max {max_duration}s, Break on silence {silence_duration}s)")
            
            # Try to find ReSpeaker / Reachy Mic
            target_device = self._get_device_index(["ReSpeaker", "UAC-2", "USB Audio", "Reachy"])
            
            if target_device is not None:
                # print(f"Recording using device index {target_device}")
                pass
            else:
                print("Recording using DEFAULT device")

            q = queue.Queue()

            def callback(indata, frames, time, status):
                if status:
                    print(status, file=sys.stderr)
                q.put(indata.copy())

            # Recording loop
            audio_buffer = []
            
            # VAD params
            silence_start_time = None
            is_speech_started = False
            start_time = time.time()
            
            with sd.InputStream(samplerate=sample_rate, device=target_device, channels=1, callback=callback, dtype='int16'):
                while True:
                    # Check max duration
                    if time.time() - start_time > max_duration:
                        print("Max duration reached.")
                        break

                    try:
                        data = q.get(timeout=0.1) # Get chunk
                    except queue.Empty:
                        continue
                        
                    audio_buffer.append(data)
                    
                    # Calculate RMS of chunk
                    # Normalize int16 to float -1..1
                    data_float = data.astype(np.float32) / 32768.0
                    rms = np.sqrt(np.mean(data_float**2))
                    
                    if rms > silence_threshold:
                        if not is_speech_started:
                            is_speech_started = True
                            print("Speech detected started.")
                        silence_start_time = None # Reset silence timer
                    else:
                        if is_speech_started:
                            if silence_start_time is None:
                                silence_start_time = time.time()
                            elif time.time() - silence_start_time > silence_duration:
                                print(f"Silence detected ({silence_duration}s). Stopping recording.")
                                break
            
            # Concatenate all chunks
            if not audio_buffer:
                return b""
                
            recording = np.concatenate(audio_buffer, axis=0)

            # Convert to WAV in-memory
            import io
            import soundfile as sf
            wav_buffer = io.BytesIO()
            sf.write(wav_buffer, recording, sample_rate, format='WAV', subtype='PCM_16')
            return wav_buffer.getvalue()
            
        except Exception as e:
            print(f"Error recording audio: {e}")
            traceback.print_exc()
            return b""

    def get_latest_frame(self) -> bytes:
        """
        Get the latest frame from the camera as JPEG bytes.
        """
        if self.mini is None:
             print("Camera DEBUG: self.mini is None")
             return None
        
        try:
            # ReachyMini has a 'media' property which is a MediaManager
            # MediaManager has a 'camera' attribute
            if not hasattr(self.mini, 'media') or self.mini.media is None:
                print("Camera DEBUG: self.mini.media is None")
                return None
                
            if self.mini.media.camera is None:
                print("Camera DEBUG: self.mini.media.camera is None")
                return None

            frame = self.mini.media.camera.read()
            if frame is None:
                print("Camera DEBUG: self.mini.media.camera.read() returned None")
                return None
            
            # Resize to smaller resolution for faster transmission and API limits
            frame = cv2.resize(frame, (320, 240))
            
            # Encode to JPEG with lower quality
            success, encoded_image = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 50])
            if success:
                # print(f"Camera DEBUG: Encoded frame {len(encoded_image.tobytes())} bytes")
                return encoded_image.tobytes()
            else:
                print("Camera DEBUG: cv2.imencode failed")
                return None
        except Exception as e:
            print(f"Error getting camera frame: {e}")
            return None
