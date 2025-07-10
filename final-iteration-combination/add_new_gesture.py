# pip install opencv-python mediapipe numpy
import cv2
import csv
import copy
import itertools
import mediapipe as mp
import numpy as np
import time
from collections import deque

# Hand tracking setup
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    max_num_hands=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)
mp_drawing = mp.solutions.drawing_utils

# Data logging setup
history_length = 16
point_history = deque(maxlen=history_length)

# Load CSV paths
keypoint_csv_path = 'model/gesture_identifier/keypoints.csv'

# Initialize variables
mode = 0  # 0: normal, 1–9: record gesture ID
number = -1

# Start video
cap = cv2.VideoCapture(0)

capture_count = 0

while cap.isOpened():
    key = cv2.waitKey(10)
    if 48 <= key <= 57:  # ASCII codes for '0' to '9'
        number = key - ord('0') # convert to number value again
        mode = 1
    elif key == 27:  # ESC to quit
        break


    ret, image = cap.read()
    if not ret:
        break

    image = cv2.flip(image, 1)  # Mirror
    debug_image = copy.deepcopy(image)
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    results = hands.process(image_rgb)

    landmark_list = []
    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            for lm in hand_landmarks.landmark:
                landmark_list.append([lm.x, lm.y])
            mp_drawing.draw_landmarks(debug_image, hand_landmarks, mp_hands.HAND_CONNECTIONS)

    if landmark_list:
        base_x, base_y = landmark_list[0][0], landmark_list[0][1]
        relative_landmarks = [[x - base_x, y - base_y] for x, y in landmark_list]
        flattened = list(itertools.chain.from_iterable(relative_landmarks))
        max_value = max(list(map(abs, flattened)))
        normalized_landmarks = [n / max_value for n in flattened]

        if mode == 1 and number != -1:
            with open(keypoint_csv_path, 'a', newline="") as f:
                writer = csv.writer(f)
                writer.writerow([number, *normalized_landmarks])
            capture_count += 1  # Increment capture count

    # Display mode, number, and capture count on screen
    cv2.putText(debug_image, f'Mode: {mode}  Number: {number}  Captures: {capture_count}', 
                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

    cv2.imshow('Gesture Capture', debug_image)

cap.release()
cv2.destroyAllWindows()
