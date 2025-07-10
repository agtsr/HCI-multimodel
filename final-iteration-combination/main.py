#pip install opencv-python speechrecognition pyaudio mediapipe pyautogui tensorflow

import cv2
import speech_recognition as sr
import threading
import os
import subprocess
import platform
import shutil
import tkinter as tk
from tkinter import ttk
from gesture_controller import GestureController



recognised_text = ""
current_path = "mocDocs"
clipboard = None
back_stack = []
forward_stack = []

# Track opened files with their process info (filename -> Popen object)
opened_files = {}

# Setting up the Tkinter GUI
class FileExplorer(tk.Tk):
    def __init__(self, root_path):
        super().__init__()
        self.title("📁 File Viewer")
        self.geometry("600x400+0+0")
        self.tree = ttk.Treeview(self)
        self.tree.heading("#0", text="Current Directory")
        self.tree.pack(fill="both", expand=True)
        self.current_path = root_path
        self.update_display()

    def update_display(self):
        self.tree.delete(*self.tree.get_children())
        self.insert_items("", self.current_path)

    def insert_items(self, parent, path):
        try:
            for item in sorted(os.listdir(path), key=str.lower):
                abs_path = os.path.join(path, item)
                node = self.tree.insert(parent, "end", text=item, open=False)
                if os.path.isdir(abs_path):
                    self.tree.insert(node, "end", text="")
        except Exception as e:
            print(f"[GUI Error] {e}")

    def refresh_on_command(self, new_path=None):
        if new_path:
            self.current_path = new_path
        self.update_display()

gui = FileExplorer(current_path)

# Global state
stream = cv2.VideoCapture(0)
if not stream.isOpened():
    print("No stream displayed!")
    exit()


#Case-insensitive search to check whether wehere base words heard match file names
def find_item_case_insensitive(base_path, target_name):
    try:
        target_name_lower = target_name.lower()
        for item in os.listdir(base_path):
            item_lower = item.lower()
            if item_lower == target_name_lower:
                return os.path.join(base_path, item)
            item_base, _ = os.path.splitext(item_lower)
            if item_base == target_name_lower:
                return os.path.join(base_path, item)
    except Exception as e:
        print(f"[Error] Cannot access {base_path}: {e}")
    return None

#Voice command parser that identifies the command the user prompted
def parse_command(text):
    text = text.lower().strip()
    text = text.replace(" dot ", ".") # Replace " dot " with "." if user mentions the file type, ".jpeg"
    if text.startswith("open "):
        return {"action": "open", "target": text[5:].strip()}
    elif text == "go back":
        return {"action": "go_back"}
    elif text == "go forward":
        return {"action": "go_forward"}
    elif text.startswith("delete "):
        return {"action": "delete", "target": text[7:].strip()}
    elif text.startswith("exit "):
        return {"action": "exit", "target": text[6:].strip()}
    return {"action": None}


def safe_refresh_on_command(new_path=None):
    def refresh():
        if new_path:
            gui.current_path = new_path
        gui.update_display()
    gui.after(0, refresh)



#Processes that are to be executed based off
def handle_command(cmd):
    global clipboard, current_path, back_stack, forward_stack, opened_files
    action = cmd.get("action")
    target = cmd.get("target", "")

    if action == "open":
        path = find_item_case_insensitive(current_path, target)
        if path and os.path.exists(path):
            if os.path.isdir(path):
                back_stack.append(current_path)
                forward_stack.clear()
                current_path = path
                safe_refresh_on_command(current_path)
            else:
                try:
                    if platform.system() == "Windows": #platform is Windows
                        proc = subprocess.Popen(["cmd", "/c", "start", "", path], shell=True)
                        opened_files[target.lower()] = proc
                    if platform.system() == "Darwin":  # platform is macOS
                        proc = subprocess.Popen(["open", path])
                        opened_files[target.lower()] = proc
                    else:  # platform is Linux or others
                        proc = subprocess.Popen(["xdg-open", path])
                        opened_files[target.lower()] = proc


                    
                    print(f"Opened '{os.path.basename(path)}'")

                except Exception as e:
                    print(f"Error opening file: {e}")

        else:
            print(f"'{target}' not found.")

    elif action == "go_back":
        if back_stack:
            forward_stack.append(current_path)
            current_path = back_stack.pop()
            safe_refresh_on_command(current_path)
            print(f"Moved back to {current_path}")
        else:
            print("No folder to go back to.")

    elif action == "go_forward":
        if forward_stack:
            back_stack.append(current_path)
            current_path = forward_stack.pop()
            safe_refresh_on_command(current_path)
            print(f"Moved forward to {current_path}")
        else:
            print("No folder to go forward to.")

    elif action == "delete":
        path = find_item_case_insensitive(current_path, target)
        if path and os.path.exists(path):
            try:
                if os.path.isfile(path):
                    os.remove(path)
                else:
                    shutil.rmtree(path)
                print(f"Deleted '{target}'")
                safe_refresh_on_command()
            except Exception as e:
                print(f"Error deleting: {e}")
        else:
            print(f"'{target}' not found.")

    elif action == "exit":
        # Exit the opened file if tracked
        key = target.lower()
        proc = opened_files.get(key)
        if proc is None:
            print(f"No tracked process for '{target}', trying to exit by taskkill if Windows...")
            if platform.system() == "Windows":
                filename = f'"{target}"'
                try:
                    # taskkill /IM "filename" /F
                    subprocess.run(["taskkill", "/IM", filename, "/F"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    print(f"Closed '{target}'")
                except subprocess.CalledProcessError:
                    print(f"Could not find or exit '{target}'.")

            elif platform.system() == "Darwin":  # macOS
                try:
                    app_name = "Preview"
                    subprocess.run(["pkill", "-x", app_name])
                    print(f"Closed app '{app_name}' associated with '{target}'")
                except Exception as e:
                    print(f"Error closing '{target}' on macOS: {e}")

            else:
                print("Unsupported OS for closing")

        else:
            try:
                proc.terminate()
                proc.wait(timeout=5)
                print(f"Closed '{target}'")
                del opened_files[key]
            except Exception as e:
                print(f"Error closing '{target}': {e}")

# Microphone that tries to identify words being said
def listen_microphone():
    global recognised_text
    recogniser = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        recogniser.adjust_for_ambient_noise(source)
        while True:
            try:
                audio = recogniser.listen(source)
                text = recogniser.recognize_google(audio)
                recognised_text = text
                print("Heard:", text)
                cmd = parse_command(text)
                if cmd["action"]:
                    handle_command(cmd)
            except sr.UnknownValueError:
                recognised_text = "[Could not understand]"
            except sr.RequestError as e:
                recognised_text = f"[Error: {e}]"


listener_thread = threading.Thread(target=listen_microphone, daemon=True)
listener_thread.start()

# Instantiate GestureController once, outside the loop
gesture_controller = GestureController()

def webcam_loop():
    ret, frame = stream.read()
    if not ret or frame is None:
        print("Failed to grab frame")
        gui.after(10, webcam_loop)
        return

    debug_image = gesture_controller.process_frame(frame)
    cv2.putText(debug_image, recognised_text, (30, 50), cv2.FONT_HERSHEY_SIMPLEX,
                0.8, (255, 0, 255), 2, cv2.LINE_AA)
    cv2.imshow("Gesture Recognition + Webcam", debug_image)
    cv2.moveWindow("Gesture Recognition + Webcam", 620, 0)  # Position right of Tkinter window


    key = cv2.waitKey(10) & 0xFF
    if key == ord('q') or key == 27:  # 'q' or ESC key
        print("Exiting program via key press.")
        gui.destroy()  # Close the Tkinter window
        return  # Exit the loop

    gui.after(10, webcam_loop)


# Start webcam loop via Tkinter
gui.after(0, webcam_loop)

# Start Tkinter mainloop (blocks, runs forever handling GUI events)
gui.mainloop()

# When GUI closes, release webcam and destroy OpenCV windows
stream.release()
cv2.destroyAllWindows()