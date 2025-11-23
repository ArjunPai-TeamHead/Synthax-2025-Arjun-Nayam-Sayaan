#!/usr/bin/env python3
import math
import time
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
            try:
                self.bus.close()
            except:
                pass
        self.bus = SMBus(self.busnum)

    def _write_byte(self, reg, val):
        self.bus.write_byte_data(self.addr, reg, val)

    def _read_byte(self, reg, tolerate=False):
        try:
            return self.bus.read_byte_data(self.addr, reg)
        except OSError:
            if tolerate:
                return 0xFF
            raise

    def _init_device(self):
        # Wake up and set basic configuration
        self._write_byte(PWR_MGMT_1, 0x01)
        time.sleep(0.05)
        self._write_byte(SMPLRT_DIV, 7)      # Sample rate divider
        self._write_byte(CONFIG, 0x03)       # DLPF config
        self._write_byte(GYRO_CONFIG, 0x00)  # ±250 dps
        self._write_byte(ACCEL_CONFIG, 0x00) # ±2g
        try:
            self._write_byte(ACCEL_CONFIG2, 0x03)
        except OSError:
            pass
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
            if self.bus:
                self.bus.close()
        except:
            pass


def compute_axis_angles(ax_g, ay_g, az_g):
    # Accel-only tilt angles for reference (not fused). Axis sign may need adjustment depending on mounting.
    eps = 1e-6
    ax_den = math.sqrt(ay_g*ay_g + az_g*az_g) + eps
    ay_den = math.sqrt(ax_g*ax_g + az_g*az_g) + eps
    az_den = math.sqrt(ax_g*ax_g + ay_g*ay_g) + eps
    angle_x = math.degrees(math.atan2(ax_g, ax_den))
    angle_y = math.degrees(math.atan2(ay_g, ay_den))
    angle_z = math.degrees(math.atan2(az_g, az_den))
    return angle_x, angle_y, angle_z


def main():
    imu = IMU(I2C_BUS, ADDR)

    # Identify device
    try:
        who = imu._read_byte(WHO_AM_I, tolerate=True)
        print(f"WHO_AM_I: 0x{who:02X}")
    except Exception as e:
        print(f"WHO_AM_I read failed: {e}")

    smooth_alpha = 0.2
    smoothed = {'x':0.0,'y':0.0,'z':0.0}

    print("\nPress Ctrl-C to stop. Streaming values...\n")
    header = (
        "time_s", "ax", "ay", "az", "gx", "gy", "gz", "tempC", "angX", "angY", "angZ", "smoothX", "smoothY", "smoothZ"
    )
    print(",".join(header))
    t0 = time.time()

    last_raw = None

    try:
        while True:
            accel, gyro, temp_c, raw = imu.read_all()
            (ax, ay, az, gx, gy, gz) = raw
            angX, angY, angZ = compute_axis_angles(accel['x'], accel['y'], accel['z'])

            # Exponential smoothing of angles
            smoothed['x'] = (1 - smooth_alpha)*smoothed['x'] + smooth_alpha*angX
            smoothed['y'] = (1 - smooth_alpha)*smoothed['y'] + smooth_alpha*angY
            smoothed['z'] = (1 - smooth_alpha)*smoothed['z'] + smooth_alpha*angZ

            now = time.time() - t0
            line = [
                f"{now:.2f}", str(ax), str(ay), str(az), str(gx), str(gy), str(gz), f"{temp_c:.2f}",
                f"{angX:.2f}", f"{angY:.2f}", f"{angZ:.2f}", f"{smoothed['x']:.2f}", f"{smoothed['y']:.2f}", f"{smoothed['z']:.2f}"
            ]
            print(",".join(line), flush=True)

            time.sleep(0.1)  # ~10 Hz update
    except KeyboardInterrupt:
        print("\nStopping...\n")
    finally:
        imu.close()
        print("Final smoothed angles:")
        print(f"X: {smoothed['x']:.2f} deg")
        print(f"Y: {smoothed['y']:.2f} deg")
        print(f"Z: {smoothed['z']:.2f} deg")

if __name__ == "__main__":
    main()