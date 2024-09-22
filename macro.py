import time
import threading
import json
import os
import ctypes
from pynput import mouse, keyboard
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController

class MouseRecorderRepeater:
    def __init__(self):
        self.mouse = MouseController()
        self.keyboard = KeyboardController()
        self.actions = []
        self.recording = False
        self.repeating = False
        self.calibrating = False
        self.exit_flag = False
        self.last_action_time = None
        self.calibration_points = []
        self.config_file = 'mouse_recorder_config.json'
        self.load_config()

    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            self.scale_x = config.get('scale_x', 1)
            self.scale_y = config.get('scale_y', 1)
            self.offset_x = config.get('offset_x', 0)
            self.offset_y = config.get('offset_y', 0)
            self.screen_width = config.get('screen_width', 1920)
            self.screen_height = config.get('screen_height', 1080)
            print(f"Loaded configuration: Scale ({self.scale_x}, {self.scale_y}), Offset ({self.offset_x}, {self.offset_y})")
        else:
            self.detect_screen_info()

    def save_config(self):
        config = {
            'scale_x': self.scale_x,
            'scale_y': self.scale_y,
            'offset_x': self.offset_x,
            'offset_y': self.offset_y,
            'screen_width': self.screen_width,
            'screen_height': self.screen_height
        }
        with open(self.config_file, 'w') as f:
            json.dump(config, f)
        print(f"Saved configuration to {self.config_file}")

    def detect_screen_info(self):
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        
        hdc = user32.GetDC(None)
        
        self.screen_width = gdi32.GetDeviceCaps(hdc, 8)  # HORZRES
        self.screen_height = gdi32.GetDeviceCaps(hdc, 10)  # VERTRES
        
        logical_width = gdi32.GetDeviceCaps(hdc, 118)  # DESKTOPHORZRES
        logical_height = gdi32.GetDeviceCaps(hdc, 117)  # DESKTOPVERTRES
        
        user32.ReleaseDC(None, hdc)
        
        self.scale_x = self.screen_width / logical_width
        self.scale_y = self.screen_height / logical_height
        self.offset_x = 0
        self.offset_y = 0

        print(f"Detected screen info: Size ({self.screen_width}x{self.screen_height}), Scale factor: ({self.scale_x}, {self.scale_y})")
        self.save_config()

    def on_press(self, key):
        try:
            if key == Key.left:
                self.toggle_recording()
            elif key == Key.right:
                self.toggle_repeating()
            elif key == Key.up:
                self.start_calibration()
            elif key == Key.down:
                print("Exiting...")
                self.exit_flag = True
                self.repeating = False
                return False  # Stop listener
        except AttributeError:
            pass

    def start_calibration(self):
        if not self.calibrating:
            print("Starting calibration. Click on the top-left corner of your screen, then the bottom-right corner.")
            self.calibrating = True
            self.calibration_points = []

    def on_click(self, x, y, button, pressed):
        if self.calibrating and pressed:
            self.calibration_points.append((x, y))
            if len(self.calibration_points) == 1:
                print("Top-left corner recorded. Now click on the bottom-right corner.")
            elif len(self.calibration_points) == 2:
                self.calculate_calibration()
                self.calibrating = False
        elif self.recording:
            current_time = time.time()
            self.actions.append(('click', x, y, button, pressed, current_time - self.last_action_time))
            self.last_action_time = current_time
            if pressed:
                print(f"Recorded {'right' if button == Button.right else 'left'} click at ({x}, {y})")

    def calculate_calibration(self):
        tl_x, tl_y = self.calibration_points[0]
        br_x, br_y = self.calibration_points[1]
        screen_width = br_x - tl_x
        screen_height = br_y - tl_y
        self.scale_x = screen_width / self.screen_width
        self.scale_y = screen_height / self.screen_height
        self.offset_x = tl_x
        self.offset_y = tl_y
        print(f"Calibration complete. Scale: ({self.scale_x}, {self.scale_y}), Offset: ({self.offset_x}, {self.offset_y})")
        self.save_config()

    def toggle_recording(self):
        if not self.recording:
            print("Recording started...")
            self.actions = []
            self.recording = True
            self.last_action_time = time.time()
        else:
            self.recording = False
            print(f"Recording stopped. {len(self.actions)} actions recorded.")

    def toggle_repeating(self):
        if not self.repeating:
            if self.actions:
                print("Replaying actions...")
                self.repeating = True
                threading.Thread(target=self.repeat_actions, daemon=True).start()
            else:
                print("No actions recorded yet.")
        else:
            self.repeating = False
            print("Replaying stopped.")

    def on_move(self, x, y):
        if self.recording:
            current_time = time.time()
            self.actions.append(('move', x, y, current_time - self.last_action_time))
            self.last_action_time = current_time

    def repeat_actions(self):
        while self.repeating and not self.exit_flag:
            for action in self.actions:
                if not self.repeating or self.exit_flag:
                    break

                time.sleep(action[-1])

                if action[0] in ('move', 'click'):
                    scaled_x = (action[1] - self.offset_x) / self.scale_x
                    scaled_y = (action[2] - self.offset_y) / self.scale_y
                    self.mouse.position = (int(scaled_x), int(scaled_y))
                    
                    if action[0] == 'click':
                        if action[4]:  # pressed
                            self.mouse.press(action[3])
                            print(f"Replayed {'right' if action[3] == Button.right else 'left'} click at ({scaled_x}, {scaled_y})")
                        else:
                            self.mouse.release(action[3])

    def run(self):
        with mouse.Listener(on_move=self.on_move, on_click=self.on_click) as mouse_listener, \
             keyboard.Listener(on_press=self.on_press) as keyboard_listener:
            
            print("Press Up Arrow key to start calibration.")
            print("Press Left Arrow key to start/stop recording.")
            print("Press Right Arrow key to start/stop replaying actions.")
            print("Press Down Arrow key to exit.")

            keyboard_listener.join()

if __name__ == "__main__":
    recorder_repeater = MouseRecorderRepeater()
    recorder_repeater.run()
