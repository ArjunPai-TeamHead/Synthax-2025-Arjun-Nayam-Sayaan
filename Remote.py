#!/usr/bin/env python3
import math
import time
import errno
import tkinter as tk
from smbus2 import SMBus, i2c_msg

I2C_BUS = 1
ADDR = 0x68

PWR_MGMT_1    = 0x6B
SMPLRT_DIV    = 0x19
CONFIG        = 0x1A
GYRO_CONFIG   = 0x1B
ACCEL_CONFIG  = 0x1C
ACCEL_CONFIG2 = 0x1D
ACCEL_XOUT_H  = 0x3B
WHO_AM_I      = 0x75

ACCEL_SCALE = 16384.0
GYRO_SCALE  = 131.0

class IMU:
    def __init__(self, busnum=I2C_BUS, addr=ADDR):
        self.busnum = busnum
        self.addr = addr
        self.bus = None
        self._open_bus()
        self._init_device()

    def _open_bus(self):
        if self.bus is not None:
            try: self.bus.close()
            except: pass
        self.bus = SMBus(self.busnum)

    def _write_byte(self, reg, val):
        self.bus.write_byte_data(self.addr, reg, val)

    def _read_byte(self, reg, tolerate=False):
        try: return self.bus.read_byte_data(self.addr, reg)
        except OSError:
            if tolerate: return 0xFF
            raise

    def _init_device(self):
        self._write_byte(PWR_MGMT_1, 0x01)
        time.sleep(0.05)
        self._write_byte(SMPLRT_DIV, 7)
        self._write_byte(CONFIG, 0x03)
        self._write_byte(GYRO_CONFIG, 0x00)
        self._write_byte(ACCEL_CONFIG, 0x00)
        try: self._write_byte(ACCEL_CONFIG2, 0x03)
        except OSError: pass
        time.sleep(0.02)

    def _read_block(self, start_reg, length):
        w = i2c_msg.write(self.addr, [start_reg])
        r = i2c_msg.read(self.addr, length)
        self.bus.i2c_rdwr(w, r)
        return list(r)

    def read_all(self):
        data = self._read_block(ACCEL_XOUT_H, 14)

        def s16(h, l):
            v = (h << 8) | l
            return v - 65536 if v & 0x8000 else v

        ax = s16(data[0],  data[1])
        ay = s16(data[2],  data[3])
        az = s16(data[4],  data[5])
        t  = s16(data[6],  data[7])
        gx = s16(data[8],  data[9])
        gy = s16(data[10], data[11])
        gz = s16(data[12], data[13])

        accel_g = {'x': ax/ACCEL_SCALE, 'y': ay/ACCEL_SCALE, 'z': az/ACCEL_SCALE}
        gyro_dps = {'x': gx/GYRO_SCALE, 'y': gy/GYRO_SCALE, 'z': gz/GYRO_SCALE}
        temp_c = t/340.0 + 36.53
        return accel_g, gyro_dps, temp_c, (ax, ay, az, gx, gy, gz)

    def close(self):
        try:
            if self.bus: self.bus.close()
        except: pass


class TiltGUI:
    def __init__(self, imu, fps=30):
        self.imu = imu
        self.root = tk.Tk()
        self.root.title("MPU Tilt (X/Y/Z)")

        self.W, self.H = 720, 420
        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg="#111")
        self.canvas.pack(fill="both", expand=True)

        self.cx = self.W // 2
        self.rows = [int(self.H*0.2), int(self.H*0.5), int(self.H*0.8)]
        self.length = 240

        self.colors = {"x": "#ff5555", "y": "#55ff55", "z": "#5599ff"}

        self.lines = {}
        self.labels = {}
        for axis, y in zip(("x","y","z"), self.rows):
            self.lines[axis] = self.canvas.create_line(0,0,0,0,width=6,fill=self.colors[axis])
            self.labels[axis] = self.canvas.create_text(
                self.W - 10, y - 14, anchor="ne", fill="#ddd",
                font=("Arial", 12), text=f"{axis.upper()}: 0.0°"
            )

        self.info = self.canvas.create_text(10,10,anchor="nw",fill="#aaa",
                                            font=("Arial",10),
                                            text="q: quit | Accel-only angles")

        self.smooth_alpha = 0.2
        self.angles = {"x":0.0,"y":0.0,"z":0.0}

        # store raw values
        self.last_ax = 0
        self.last_ay = 0
        self.last_az = 0
        self.last_gx = 0
        self.last_gy = 0
        self.last_gz = 0
        self.last_temp = 0.0
        self.last_angle_x = 0.0
        self.last_angle_y = 0.0
        self.last_angle_z = 0.0

        self.period_ms = int(1000/fps)
        self.root.bind("<q>", lambda e: self.root.quit())
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._running = True
        self.update_gui()

    def compute_axis_angles(self, ax, ay, az):
        eps = 1e-6
        ax_den = math.sqrt(ay*ay + az*az) + eps
        ay_den = math.sqrt(ax*ax + az*az) + eps
        az_den = math.sqrt(ax*ax + ay*ay) + eps
        angle_x = math.degrees(math.atan2(ax, ax_den))
        angle_y = math.degrees(math.atan2(ay, ay_den))
        angle_z = math.degrees(math.atan2(az, az_den))
        return angle_x, angle_y, angle_z

    def draw_line(self, axis, angle_deg, y):
        L = self.length/2
        t = math.radians(angle_deg)
        x0 = self.cx - L*math.cos(t)
        y0 = y    - L*math.sin(t)
        x1 = self.cx + L*math.cos(t)
        y1 = y    + L*math.sin(t)
        self.canvas.coords(self.lines[axis], x0,y0,x1,y1)
        self.canvas.itemconfigure(self.labels[axis], text=f"{axis.upper()}: {angle_deg:+.1f}°")

    def update_gui(self):
        if not self._running:
            return
        try:
            accel, gyro, temp_c, raw = self.imu.read_all()
            (ax, ay, az, gx, gy, gz) = raw

            # store raw values
            self.last_ax, self.last_ay, self.last_az = ax, ay, az
            self.last_gx, self.last_gy, self.last_gz = gx, gy, gz
            self.last_temp = temp_c

            angle_x, angle_y, angle_z = self.compute_axis_angles(
                accel["x"], accel["y"], accel["z"]
            )

            self.last_angle_x = angle_x
            self.last_angle_y = angle_y
            self.last_angle_z = angle_z

            for axis, val in zip(("x","y","z"),(angle_x,angle_y,angle_z)):
                self.angles[axis] = (1-self.smooth_alpha)*self.angles[axis] + self.smooth_alpha*val

            for axis, y in zip(("x","y","z"), self.rows):
                self.draw_line(axis, self.angles[axis], y)

        except:
            pass

        self.root.after(self.period_ms, self.update_gui)

    def on_close(self):
        self._running = False
        try: self.imu.close()
        finally: self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    imu = IMU(I2C_BUS, ADDR)
    app = TiltGUI(imu, fps=30)
    app.run()

    print("\n=== FINAL VALUES ===")
    print(f"ax = {app.last_ax}")
    print(f"ay = {app.last_ay}")
    print(f"az = {app.last_az}")

    print(f"gx = {app.last_gx}")
    print(f"gy = {app.last_gy}")
    print(f"gz = {app.last_gz}")

    print(f"temp_c = {app.last_temp:.2f}")

    print(f"angle_x = {app.last_angle_x:.2f}")
    print(f"angle_y = {app.last_angle_y:.2f}")
    print(f"angle_z = {app.last_angle_z:.2f}")

    print(f"smoothed_x = {app.angles['x']:.2f}")
    print(f"smoothed_y = {app.angles['y']:.2f}")
    print(f"smoothed_z = {app.angles['z']:.2f}")

if __name__ == "__main__":
    main()
