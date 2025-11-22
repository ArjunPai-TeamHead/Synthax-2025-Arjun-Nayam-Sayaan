import socket
from adafruit_pca9685 import PCA9685
import board
import busio
import time

i2c = busio.I2C(board.SCL, board.SDA)
pca = PCA9685(i2c)
pca.frequency = 50

# Motor mapping (change if reversed)
LEFT_FWD = 0
LEFT_REV = 1
RIGHT_FWD = 2
RIGHT_REV = 3

# Servo channels
SERVO_CHANNELS = [4,5,6,7,8,9,10,11]

def set_motor(channel, duty):
    duty = max(0, min(100, duty))
    pca.channels[channel].duty_cycle = int(duty * 65535 / 100)

def move(left, right):
    if left >= 0:
        set_motor(LEFT_FWD, left)
        set_motor(LEFT_REV, 0)
    else:
        set_motor(LEFT_FWD, 0)
        set_motor(LEFT_REV, -left)

    if right >= 0:
        set_motor(RIGHT_FWD, right)
        set_motor(RIGHT_REV, 0)
    else:
        set_motor(RIGHT_FWD, 0)
        set_motor(RIGHT_REV, -right)

def stop_all():
    for ch in [LEFT_FWD, LEFT_REV, RIGHT_FWD, RIGHT_REV]:
        set_motor(ch, 0)

def set_servo(index, angle):
    if index < 0 or index >= len(SERVO_CHANNELS):
        return
    ch = SERVO_CHANNELS[index]
    pulse_min = 1000
    pulse_max = 2000
    pulse = pulse_min + (angle/180)*(pulse_max - pulse_min)
    duty = int((pulse / 20000) * 65535)
    pca.channels[ch].duty_cycle = duty

s = socket.socket()
s.bind(("0.0.0.0", 9000))
s.listen(1)

print("Waiting for connection...")
conn, addr = s.accept()
print("Connected:", addr)

while True:
    data = conn.recv(1024).decode().strip()
    if not data:
        continue

    parts = data.split()

    if parts[0] == "MOVE":
        move(int(parts[1]), int(parts[2]))

    elif parts[0] == "STOP":
        stop_all()

    elif parts[0] == "SERVO":
        idx = int(parts[1])
        ang = int(parts[2])
        set_servo(idx, ang)
