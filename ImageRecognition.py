import time
import cv2
import numpy as np
from picamera2 import Picamera2
from ultralytics import YOLO

def run():
    # 1. Initialize YOLO Model
    print("[*] Loading YOLOv8 model...")
    model = YOLO('yolov8n.pt')

    # 2. Initialize Picamera2
    print("[*] Starting Picamera2...")
    picam2 = Picamera2()

    # FIX: Use 'create_video_configuration' instead of 'create_configuration'
    # We request BGR888 format so OpenCV can use it directly without conversion
    config = picam2.create_video_configuration(
        main={"size": (640, 480), "format": "BGR888"}
    )
    
    picam2.configure(config)
    picam2.start()

    print("[*] Running. Press 'q' to exit.")

    try:
        while True:
            # 3. Capture a frame
            # capture_array() returns the image as a numpy array (Height, Width, Colors)
            frame = picam2.capture_array()

            # 4. Run AI Inference
            results = model(frame, stream=True, verbose=False)

            # 5. Draw Detections
            for r in results:
                boxes = r.boxes
                for box in boxes:
                    # Coordinates
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    
                    # Label info
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    name = model.names[cls]
                    label = f"{name} {conf:.2f}"

                    # Draw Box and Label
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, label, (x1, y1 - 10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            # 6. Display
            cv2.imshow("YOLOv8 - RPiCam", frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except Exception as e:
        print(f"[-] Error: {e}")
    finally:
        picam2.stop()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run()