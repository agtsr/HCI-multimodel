# gesture_controller.py

import cv2
import numpy as np
import mediapipe as mp
import itertools
import csv
import pyautogui
import platform

from model import GestureIdentifier  # Make sure model.py exists and works

class GestureController:
    def __init__(self):
        # Load model and labels
        self.classifier = GestureIdentifier()
        with open('model/gesture_identifier/gesture_labels.csv', encoding='utf-8-sig') as f:
            self.labels = [row[0] for row in csv.reader(f)]

        # MediaPipe setup
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5
        )
        self.mp_drawing = mp.solutions.drawing_utils

        # Dynamic gesture state
        self.prev_fist_y = None
        self.prev_pointer_x = None
        self.prev_pinch_gap = None
        self.yScrollFactor = 0.1
        self.xScrollFactor = 0.1
        pass

    def process_frame(self, frame):
        debug_image = frame.copy()
        image_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(image_rgb)

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                preprocessed = self.preprocess_landmarks(hand_landmarks, frame.shape)
                confidence = self.classifier.predict_confidence(preprocessed)
                gesture_id = self.classifier(preprocessed)
                gesture_name = self.labels[gesture_id]

                self.mp_drawing.draw_landmarks(debug_image, hand_landmarks, self.mp_hands.HAND_CONNECTIONS)
                coordinates = self.draw_gesture_info(debug_image, hand_landmarks, frame.shape, gesture_name)
                self.draw_gesture_confidences(debug_image, confidence)
                self.handle_gesture(gesture_name, coordinates, hand_landmarks, frame.shape)
        else:
            # Reset states if no hands detected
            self.prev_fist_y = None
            self.prev_pointer_x = None
            self.prev_pinch_gap = None

        return debug_image

    

    def preprocess_landmarks(self, landmarks, image_shape):
        image_width, image_height = image_shape[1], image_shape[0]
        landmark_list = [[int(lm.x * image_width), int(lm.y * image_height)] for lm in landmarks.landmark]
        base_x, base_y = landmark_list[0]
        relative = [[x - base_x, y - base_y] for x, y in landmark_list]
        flattened = list(itertools.chain.from_iterable(relative))
        max_val = max(map(abs, flattened)) or 1
        return [n / max_val for n in flattened]

    def draw_gesture_info(self, image, hand_landmarks, image_shape, gesture_name):
        image_width, image_height = image_shape[1], image_shape[0]
        xs = [int(lm.x * image_width) for lm in hand_landmarks.landmark]
        ys = [int(lm.y * image_height) for lm in hand_landmarks.landmark]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        cv2.rectangle(image, (x_min, y_min), (x_max, y_max), (0, 255, 0), 2)
        text_pos = (x_min, y_min - 10 if y_min - 10 > 10 else y_min + 20)
        cv2.putText(image, gesture_name, text_pos, cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        return (x_min + x_max) // 2, (y_min + y_max) // 2

    def draw_gesture_confidences(self, image, confidence_values, top_left=(10, 30), line_height=25):
        sorted_items = sorted(zip(self.labels, confidence_values), key=lambda x: x[1], reverse=True)
        for i, (label, confidence) in enumerate(sorted_items):
            text = f"{label}: {confidence:.2f}"
            position = (top_left[0], top_left[1] + i * line_height)
            cv2.putText(image, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    def get_pinch_gap(self, thumb_tip, index_tip, image_shape):
        w, h = image_shape[1], image_shape[0]
        x1, y1 = int(thumb_tip.x * w), int(thumb_tip.y * h)
        x2, y2 = int(index_tip.x * w), int(index_tip.y * h)
        return np.linalg.norm(np.array([x2 - x1, y2 - y1]))



    def handle_gesture(self, gesture_name, coordinates, hand_landmarks, image_shape):
        
        if gesture_name == "Fist":
            
            if self.prev_fist_y is not None:
                dy = int(coordinates[1] - self.prev_fist_y)
                if abs(dy) >= 1:
                    pyautogui.scroll(dy)
                    print("Fist moved — scrolling") 
                    
            self.prev_fist_y = coordinates[1]
        else:
            self.prev_fist_y = None


        if gesture_name == "Swipe":
            if platform.system() == 'Darwin':
                pointer_x = int(hand_landmarks.landmark[8].x * image_shape[1])

                if self.prev_pointer_x is not None:
                    dx = int(pointer_x - self.prev_pointer_x)
                    if abs(dx) >= 5:
                        pyautogui.hscroll(int(dx))
                        print("Swipe detected — horizontal scroll")

                self.prev_pointer_x = pointer_x
            else:
                print('Horizontal Scroll only on mac')
        else:
            self.prev_pointer_x = None




        if gesture_name == "Pinch":
            thumb_tip = hand_landmarks.landmark[4]
            index_tip = hand_landmarks.landmark[8]
            pinch_gap = self.get_pinch_gap(thumb_tip, index_tip, image_shape)

            if self.prev_pinch_gap is not None:
                delta = pinch_gap - self.prev_pinch_gap
                if delta < -50:
                    if platform.system() == 'Darwin':
                        pyautogui.hotkey('command', '-')
                    else:
                        pyautogui.hotkey('ctrl', '-')
                    print("Pinched — zooming out")
                elif delta > 50:
                    if platform.system() == 'Darwin':
                        pyautogui.hotkey('command', '+')
                    else:
                        pyautogui.hotkey('ctrl', '+')
                    print("Unpinched — zooming in")


            self.prev_pinch_gap = pinch_gap
        else:
            self.prev_pinch_gap = None



# Run directly as a script
if __name__ == "__main__":
    controller = GestureController()
    controller.run()
