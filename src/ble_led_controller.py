import asyncio
import threading
import logging
from bleak import BleakClient, BleakScanner

logger = logging.getLogger(__name__)

# --- BLE Configuration ---
BLE_SERVICE_UUID = "4fafc201-1sb5-45ae-3fcc-c5c9c331914b"
BLE_CHARACTERISTIC_UUID = "ceb5483e-36e1-2688-b7f5-ea07361d26a8"
BLE_DEVICE_NAME = "LED"

class BLELedController:
    """
    Controller for BLE LED device.
    Manages connection and sends commands via a queue.
    """
    
    def __init__(self):
        self.client = None
        self.connected = False
        self.loop = None
        self.thread = None
        self._command_queue = asyncio.Queue()
        self._stop_event = asyncio.Event()
    
    def start(self):
        """Starts the BLE connection loop in a background thread."""
        if self.thread and self.thread.is_alive():
            logger.warning("BLELedController thread already running.")
            return

        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
    
    def _run_loop(self):
        """Runs the asyncio event loop for BLE operations."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        try:
            self.loop.run_until_complete(self._ble_main())
        except Exception as e:
            logger.error(f"BLE Loop Error: {e}")
        finally:
            self.loop.close()
    
    async def _ble_main(self):
        """Main BLE connection and command processing loop."""
        logger.info(f"Scanning for BLE device '{BLE_DEVICE_NAME}'...")
        
        try:
            device = await BleakScanner.find_device_by_name(BLE_DEVICE_NAME, timeout=10.0)
            
            if device is None:
                logger.warning(f"BLE device '{BLE_DEVICE_NAME}' not found. LED control disabled.")
                return
            
            logger.info(f"Found BLE device: {device.name} ({device.address})")
            
            async with BleakClient(device) as client:
                self.client = client
                self.connected = True
                logger.info("BLE Connected successfully.")
                
                # Command loop
                while not self._stop_event.is_set() and client.is_connected:
                    try:
                        # Wait for command with timeout to allow checking stop event/connection
                        command = await asyncio.wait_for(self._command_queue.get(), timeout=1.0)
                        
                        logger.debug(f"Sending BLE command: {command}")
                        await client.write_gatt_char(BLE_CHARACTERISTIC_UUID, command.encode("utf-8"))
                        self._command_queue.task_done()
                        
                    except asyncio.TimeoutError:
                        continue
                    except Exception as e:
                        logger.error(f"BLE Send Error: {e}")
                        # If simple error, continue. If connection lost, loop will exit.
                        if not client.is_connected:
                            logger.error("BLE Connection lost.")
                            break
                            
        except Exception as e:
            logger.error(f"BLE Connection/Runtime Error: {e}")
        finally:
            self.connected = False
            logger.info("BLE Controller stopped.")

    def send(self, command: str):
        """
        Enqueues a command to be sent to the LED.
        Thread-safe method called from main application.
        """
        # If loop is running, use call_soon_threadsafe
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self._command_queue.put_nowait, command)
        else:
             logger.warning("BLE loop not running, cannot send command.")

    def stop(self):
        """Stops the BLE controller."""
        if self.loop:
            self.loop.call_soon_threadsafe(self._stop_event.set)
        if self.thread:
            self.thread.join(timeout=2.0)
