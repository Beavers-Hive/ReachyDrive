from reachy_mini import ReachyMini
import sys

try:
    mini = ReachyMini()
    print("ReachyMini initialized.")
    print("Attributes:", dir(mini))
    if hasattr(mini, 'camera'):
        print("Camera attributes:", dir(mini.camera))
except Exception as e:
    print(f"Error: {e}")
