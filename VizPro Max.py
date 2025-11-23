import google.generativeai as genai
import speech_recognition as mic
import pyttsx3
import time
import cv2
import numpy as np
from picamera2 import Picamera2
from ultralytics import YOLO
import threading
from PIL import Image

# --- Configuration ---
API_KEY = "AIzaSyAOGcHUhB4ODfGvT9EsCEYYUqZlDR9TCVs"
MODEL_NAME = "gemini-2.0-flash-lite"

# --- Global Shared Data ---
# These variables are shared between the Camera Thread and Main Thread
latest_frame = None
current_detected_objects = []
frame_lock = threading.Lock() # Prevents reading the image while it's being written

# --- Vision System (Runs in Background) ---
def vision_loop():
    global current_detected_objects, latest_frame
    
    print("[*] Loading YOLOv8 model...")
    yolo_model = YOLO('yolov8n.pt')

    print("[*] Starting Picamera2...")
    picam2 = Picamera2()
    # BGR888 is standard for OpenCV
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "BGR888"}
    )
    picam2.configure(config)
    picam2.start()
    
    print("[*] Vision system active.")

    try:
        while True:
            # 1. Capture raw array
            frame = picam2.capture_array()
            
            # 2. Run YOLO Inference locally (fast object tags)
            results = yolo_model(frame, stream=True, verbose=False)
            
            temp_objects = []
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Draw bounding boxes for the local display
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    cls = int(box.cls[0])
                    name = yolo_model.names[cls]
                    temp_objects.append(name)
                    
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, name, (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 3. Update Global Data securely
            with frame_lock:
                latest_frame = frame.copy() # Save a copy for the AI to grab later
                current_detected_objects = list(set(temp_objects))

            # 4. Local Display (Optional)
            cv2.imshow("Ruma Vision Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"[-] Vision Error: {e}")
    finally:
        picam2.stop()
        cv2.destroyAllWindows()

# --- AI & Voice System (Main Thread) ---
def main_loop():
    speech = mic.Recognizer()
    engine = pyttsx3.init()
    engine.setProperty('rate', 150)
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)

    # Configure Gemini
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)

    base_instruction = (
        "You are Ruma, a robotic dog AI. Respond in a friendly, concise way. "
        "I am sending you an image of what I see right now, along with a list of objects detected by my sensors. "
        "Use the image to answer questions like 'What color is the shirt?' or 'Is the person smiling?'. "
        "If asked to move, output a command like Forward(seconds), Left(angle), etc. "
    )

    engine.say("Ruma is ready. Watching and listening.")
    engine.runAndWait()

    while True:
        try:
            with mic.Microphone() as source:
                speech.adjust_for_ambient_noise(source, duration=0.5)
                print("\n[Listening...]")
                audio = speech.listen(source)
            
            try:
                user_text = speech.recognize_google(audio)
                print(f"User: {user_text}")

                # --- Prepare Data for Gemini ---
                pil_image = None
                yolo_context = "None"

                # Grab the latest visual data safely
                with frame_lock:
                    if latest_frame is not None:
                        # OpenCV uses BGR, Gemini needs RGB
                        rgb_frame = cv2.cvtColor(latest_frame, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(rgb_frame)
                    
                    if current_detected_objects:
                        yolo_context = ", ".join(current_detected_objects)

                print(f"[Sending to AI] Text: '{user_text}' | YOLO Tags: {yolo_context} | Image: {'Yes' if pil_image else 'No'}")

                # Construct the multimodal prompt
                # We pass the text prompt AND the image object in a list
                prompt_parts = [
                    f"{base_instruction}\n"
                    f"YOLO SENSOR DATA: {yolo_context}\n"
                    f"USER REQUEST: {user_text}",
                    pil_image  # The actual image object
                ]

                # Generate response
                response = model.generate_content(prompt_parts)
                ai_reply = response.text
                
                print(f"Ruma: {ai_reply}")
                engine.say(ai_reply)
                engine.runAndWait()

            except mic.UnknownValueError:
                pass # Ignore silence
            except mic.RequestError:
                engine.say("I am having trouble connecting to the internet.")
                engine.runAndWait()

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    # 1. Start Vision Thread
    t = threading.Thread(target=vision_loop, daemon=True)
    t.start()
    
    # 2. Warmup
    time.sleep(2)
    
    # 3. Start Main Interaction Loop
    main_loop()