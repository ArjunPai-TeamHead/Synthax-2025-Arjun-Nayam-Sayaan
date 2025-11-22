import socket

JETSON_IP = "192.168.1.100"   # change this
PORT = 9000

s = socket.socket()
s.connect((JETSON_IP, PORT))

print("Connected to Jetson.")

while True:
    cmd = input("> ")
    s.send(cmd.encode())
