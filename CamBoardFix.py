import cv2
import mediapipe as mp
import time
import numpy as np
from pynput.keyboard import Controller, Key
from pynput.mouse import Button, Controller as MouseController
import pyautogui
import win32gui
import win32con

# Ініціалізація Mediapipe
mp_pose = mp.solutions.pose
mp_drawing = mp.solutions.drawing_utils
pose = mp_pose.Pose(min_detection_confidence=0.7, min_tracking_confidence=0.7)

# Ініціалізація для керування клавіатурою та мишею
keyboard = Controller()
mouse = MouseController()

# Налаштування відображення
show_skeleton = True
screen_width, screen_height = pyautogui.size()

# Змінні для відстеження стану
right_hand_moving = False
head_tilt_left = False
head_tilt_right = False
right_knee_lifted = False
left_button_pressed = False
right_button_pressed = False
program_running = True

# Мертві зони
WASD_DEADZONE = 0.03
MOUSE_DEADZONE = 0.02
MOUSE_SENSITIVITY = 1.0
HEAD_TILT_THRESHOLD = 0.07

# Початкові координати для калібрування миші
initial_left_shoulder_x = 0
initial_left_shoulder_y = 0
initial_left_wrist_x = 0
initial_left_wrist_y = 0
calibrated = False

# Словник для відстеження стану клавіш WASD
wasd_keys = {'w': False, 'a': False, 's': False, 'd': False}

# Функція для встановлення вікна поверх інших
def set_window_topmost(window_name):
    hwnd = win32gui.FindWindow(None, window_name)
    if hwnd:
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                              win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)

# Функція для емуляції WASD з покращеною мертвою зоною
def emulate_wasd(landmarks):
    global right_hand_moving, wasd_keys
    
    # Визначення координат правої руки
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    right_elbow = landmarks[mp_pose.PoseLandmark.RIGHT_ELBOW]
    right_wrist = landmarks[mp_pose.PoseLandmark.RIGHT_WRIST]
    
    # Визначення напрямку руху
    dx = right_wrist.x - right_elbow.x
    dy = right_wrist.y - right_elbow.y
    
    # Визначення активних клавіш з мертвою зоною
    active_keys = []
    
    # Визначаємо активні клавіші тільки якщо вийшли за межі мертвої зони
    if dy < -WASD_DEADZONE:  # Рух вгору
        active_keys.append('w')
    elif dy > WASD_DEADZONE:  # Рух вниз
        active_keys.append('s')
    
    if dx < -WASD_DEADZONE:  # Рух вліво
        active_keys.append('a')
    elif dx > WASD_DEADZONE:  # Рух вправо
        active_keys.append('d')
    
    # Обробка змін стану клавіш
    for key in ['w', 'a', 's', 'd']:
        if key in active_keys and not wasd_keys[key]:
            keyboard.press(key)
            wasd_keys[key] = True
        elif key not in active_keys and wasd_keys[key]:
            keyboard.release(key)
            wasd_keys[key] = False
    
    # Оновлення стану руху руки
    right_hand_moving = len(active_keys) > 0

# Функція для калібрування миші
def calibrate_mouse(landmarks):
    global initial_left_shoulder_x, initial_left_shoulder_y
    global initial_left_wrist_x, initial_left_wrist_y, calibrated
    
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
    
    initial_left_shoulder_x = left_shoulder.x
    initial_left_shoulder_y = left_shoulder.y
    initial_left_wrist_x = left_wrist.x
    initial_left_wrist_y = left_wrist.y
    calibrated = True

# Функція для емуляції руху миші з покращеною мертвою зоною та чутливістю
def emulate_mouse(landmarks):
    global calibrated
    
    if not calibrated:
        calibrate_mouse(landmarks)
        return
    
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    left_wrist = landmarks[mp_pose.PoseLandmark.LEFT_WRIST]
    
    # Обчислення відносних змін положення
    dx = (left_wrist.x - initial_left_wrist_x) - (left_shoulder.x - initial_left_shoulder_x)
    dy = (left_wrist.y - initial_left_wrist_y) - (left_shoulder.y - initial_left_shoulder_y)
    
    # Застосування мертвої зони
    if abs(dx) < MOUSE_DEADZONE:
        dx = 0
    if abs(dy) < MOUSE_DEADZONE:
        dy = 0
    
    # Масштабування змін для екрану (зверніть увагу на знак для dy - інвертуємо напрямок вгору/вниз)
    move_x = dx * screen_width * MOUSE_SENSITIVITY
    move_y = -dy * screen_height * MOUSE_SENSITIVITY  # Інвертуємо dy для природнього руху
    
    # Переміщення миші
    if abs(move_x) > 0.1 or abs(move_y) > 0.1:
        mouse.move(move_x, move_y)

# Функція для визначення нахилу голови з мертвою зоною
def check_head_tilt(landmarks):
    global head_tilt_left, head_tilt_right, left_button_pressed, right_button_pressed
    
    nose = landmarks[mp_pose.PoseLandmark.NOSE]
    left_shoulder = landmarks[mp_pose.PoseLandmark.LEFT_SHOULDER]
    right_shoulder = landmarks[mp_pose.PoseLandmark.RIGHT_SHOULDER]
    
    # Середнє положення плечей
    shoulder_center_x = (left_shoulder.x + right_shoulder.x) / 2
    
    # Визначення нахилу голови з мертвою зоною
    new_head_tilt_left = nose.x < shoulder_center_x - HEAD_TILT_THRESHOLD
    new_head_tilt_right = nose.x > shoulder_center_x + HEAD_TILT_THRESHOLD
    
    # Емуляція кліків мишею
    if new_head_tilt_left and not left_button_pressed:
        mouse.press(Button.left)
        left_button_pressed = True
    elif not new_head_tilt_left and left_button_pressed:
        mouse.release(Button.left)
        left_button_pressed = False
    
    if new_head_tilt_right and not right_button_pressed:
        mouse.press(Button.right)
        right_button_pressed = True
    elif not new_head_tilt_right and right_button_pressed:
        mouse.release(Button.right)
        right_button_pressed = False

# Функція для перевірки підняття коліна
def check_knee_lift(landmarks):
    global right_knee_lifted
    
    right_hip = landmarks[mp_pose.PoseLandmark.RIGHT_HIP]
    right_knee = landmarks[mp_pose.PoseLandmark.RIGHT_KNEE]
    
    # Перевірка, чи коліно вище за стегно
    knee_lifted = right_knee.y < right_hip.y - 0.05
    
    # Емуляція натискання Shift
    if knee_lifted and not right_knee_lifted:
        keyboard.press(Key.shift)
        right_knee_lifted = True
    elif not knee_lifted and right_knee_lifted:
        keyboard.release(Key.shift)
        right_knee_lifted = False

# Функція для малювання оверлею
def draw_overlay(frame, actions):
    h, w, _ = frame.shape
    
    # Малювання кнопок WASD
    button_size = 60
    margin = 20
    start_x = w - button_size * 2 - margin * 2
    start_y = h - button_size * 3 - margin * 2
    
    # Кнопка W (вгору)
    color_w = (0, 255, 0) if 'w' in actions else (100, 100, 100)
    cv2.rectangle(frame, 
                 (start_x + button_size, start_y), 
                 (start_x + button_size * 2, start_y + button_size), 
                 color_w, -1)
    cv2.putText(frame, 'W', (start_x + button_size + 25, start_y + 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Кнопка A (ліворуч)
    color_a = (0, 255, 0) if 'a' in actions else (100, 100, 100)
    cv2.rectangle(frame, 
                 (start_x, start_y + button_size), 
                 (start_x + button_size, start_y + button_size * 2), 
                 color_a, -1)
    cv2.putText(frame, 'A', (start_x + 25, start_y + button_size + 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Кнопка S (вниз)
    color_s = (0, 255, 0) if 's' in actions else (100, 100, 100)
    cv2.rectangle(frame, 
                 (start_x + button_size, start_y + button_size), 
                 (start_x + button_size * 2, start_y + button_size * 2), 
                 color_s, -1)
    cv2.putText(frame, 'S', (start_x + button_size + 25, start_y + button_size + 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Кнопка D (праворуч)
    color_d = (0, 255, 0) if 'd' in actions else (100, 100, 100)
    cv2.rectangle(frame, 
                 (start_x + button_size * 2, start_y + button_size), 
                 (start_x + button_size * 3, start_y + button_size * 2), 
                 color_d, -1)
    cv2.putText(frame, 'D', (start_x + button_size * 2 + 25, start_y + button_size + 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    # Індикатор Shift
    color_shift = (0, 255, 0) if right_knee_lifted else (100, 100, 100)
    cv2.rectangle(frame, (20, h - 50), (170, h - 10), color_shift, -1)
    cv2.putText(frame, 'SHIFT', (40, h - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Індикатор ЛКМ
    color_lmb = (0, 255, 0) if left_button_pressed else (100, 100, 100)
    cv2.rectangle(frame, (200, h - 50), (350, h - 10), color_lmb, -1)
    cv2.putText(frame, 'LMB', (220, h - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Індикатор ПКМ
    color_rmb = (0, 255, 0) if right_button_pressed else (100, 100, 100)
    cv2.rectangle(frame, (380, h - 50), (530, h - 10), color_rmb, -1)
    cv2.putText(frame, 'RMB', (400, h - 20), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Кнопка перемикання скелету
    color_toggle = (100, 200, 100) if show_skeleton else (100, 100, 200)
    cv2.rectangle(frame, (w - 200, 20), (w - 20, 70), color_toggle, -1)
    cv2.putText(frame, 'Toggle Skeleton', (w - 190, 50), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    # Кнопка виходу
    cv2.rectangle(frame, (w - 200, 80), (w - 20, 130), (200, 100, 100), -1)
    cv2.putText(frame, 'Exit', (w - 100, 110), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Відображення параметрів
    cv2.putText(frame, f"Mouse Sensitivity: {MOUSE_SENSITIVITY}", (20, 40), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
    cv2.putText(frame, f"WASD Deadzone: {WASD_DEADZONE}", (20, 70), 
               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

# Головна програма
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("Помилка: не вдалося відкрити камеру!")
    exit()

# Створення вікна
cv2.namedWindow('Game Controller', cv2.WINDOW_NORMAL)
cv2.resizeWindow('Game Controller', 1280, 720)

# Встановлення вікна поверх інших
set_window_topmost('Game Controller')

toggle_button_pressed_time = 0
exit_button_pressed_time = 0
toggle_button_cooldown = 0

try:
    while program_running:
        ret, frame = cap.read()
        if not ret:
            print("Помилка: не вдалося отримати кадр з камери!")
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (1280, 720))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = pose.process(rgb_frame)
        current_time = time.time()
        
        actions = []
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark
            
            # Відображення скелета
            if show_skeleton:
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS,
                    mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2),
                    mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2)
                )
            
            # Обробка рухів
            emulate_wasd(landmarks)
            emulate_mouse(landmarks)
            check_head_tilt(landmarks)
            check_knee_lift(landmarks)
            
            # Визначення активних дій для оверлею
            for key, pressed in wasd_keys.items():
                if pressed:
                    actions.append(key)
        
        # Малювання оверлею
        draw_overlay(frame, actions)
        
        # Перевірка натискання кнопок
        mouse_x, mouse_y = mouse.position
        toggle_button_x = frame.shape[1] - 200
        toggle_button_y = 20
        exit_button_y = 80
        
        # Кнопка перемикання скелету
        if (toggle_button_x <= mouse_x <= toggle_button_x + 180 and 
            toggle_button_y <= mouse_y <= toggle_button_y + 50):
            if toggle_button_pressed_time == 0:
                toggle_button_pressed_time = current_time
            elif current_time - toggle_button_pressed_time > 2 and current_time > toggle_button_cooldown:
                show_skeleton = not show_skeleton
                toggle_button_pressed_time = 0
                toggle_button_cooldown = current_time + 1  # Затримка 1 секунда
        else:
            toggle_button_pressed_time = 0
        
        # Кнопка виходу
        if (toggle_button_x <= mouse_x <= toggle_button_x + 180 and 
            exit_button_y <= mouse_y <= exit_button_y + 50):
            if exit_button_pressed_time == 0:
                exit_button_pressed_time = current_time
            elif current_time - exit_button_pressed_time > 2:
                program_running = False
        else:
            exit_button_pressed_time = 0
        
        # Відображення вікна
        cv2.imshow('Game Controller', frame)
        
        # Вихід з програми при натисканні 'q' або Esc
        key = cv2.waitKey(1)
        if key == ord('q') or key == 27:  # 27 - це клавіша Esc
            program_running = False

except Exception as e:
    print(f"Сталася помилка: {e}")

finally:
    # Відпустити всі клавіші при виході
    for key, pressed in wasd_keys.items():
        if pressed:
            keyboard.release(key)
    
    keyboard.release(Key.shift)
    if left_button_pressed:
        mouse.release(Button.left)
    if right_button_pressed:
        mouse.release(Button.right)
    
    cap.release()
    cv2.destroyAllWindows()
    print("Програма успішно завершена")
