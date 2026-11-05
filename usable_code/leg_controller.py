#!/usr/bin/env python3
import argparse
import os
import socket
import sys
import time
import pigpio

# Default Servo Pulse Width Limits (in microseconds)
# Standard servos: 500us (0 deg) to 2500us (180 deg), center = 1500us (90 deg)
PULSE_MIN = 500
PULSE_MAX = 2500
PULSE_CENTER = 1500

# Servo movement step size (microseconds per command tick)
ANGLE_STEP = 50  

class LegController:
    def __init__(self, ud_pin: int, lr_pin: int, socket_path: str):
        self.ud_pin = ud_pin
        self.lr_pin = lr_pin
        self.socket_path = socket_path

        # Current pulse widths
        self.ud_pulse = PULSE_CENTER
        self.lr_pulse = PULSE_CENTER

        # Initialize pigpio
        self.pi = pigpio.pi()
        if not self.pi.connected:
            print("Error: Could not connect to pigpiod daemon. Run 'sudo pigpiod' first.")
            sys.exit(1)

        # Set pin modes
        self.pi.set_mode(self.ud_pin, pigpio.OUTPUT)
        self.pi.set_mode(self.lr_pin, pigpio.OUTPUT)

        # Initialize servos to neutral position
        self._update_servos()

    def _update_servos(self):
        """Send PWM pulse width signals to pigpio."""
        # Clamp pulse widths within safe physical bounds
        self.ud_pulse = max(PULSE_MIN, min(PULSE_MAX, self.ud_pulse))
        self.lr_pulse = max(PULSE_MIN, min(PULSE_MAX, self.lr_pulse))

        self.pi.set_servo_pulsewidth(self.ud_pin, self.ud_pulse)
        self.pi.set_servo_pulsewidth(self.lr_pin, self.lr_pulse)

    def process_command(self, cmd: str):
        """
        Translates commands:
        'U' / 'D': Up / Down (vertical servo)
        'L' / 'R': Left / Right (horizontal servo)
        'CENTER': Reset leg to default neutral position
        """
        cmd = cmd.strip().upper()

        if cmd == 'U':
            self.ud_pulse += ANGLE_STEP
        elif cmd == 'D':
            self.ud_pulse -= ANGLE_STEP
        elif cmd == 'L':
            self.lr_pulse += ANGLE_STEP
        elif cmd == 'R':
            self.lr_pulse -= ANGLE_STEP
        elif cmd == 'CENTER':
            self.ud_pulse = PULSE_CENTER
            self.lr_pulse = PULSE_CENTER
        else:
            print(f"Unknown command received: {cmd}")
            return

        self._update_servos()

    def run(self):
        """Sets up Unix Domain Socket server to receive commands from Master."""
        # Clean up stale socket file if it exists
        if os.path.exists(self.socket_path):
            os.remove(self.socket_path)

        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        server.bind(self.socket_path)

        print(f"Leg Controller online -> U/D Pin: {self.ud_pin}, L/R Pin: {self.lr_pin} | IPC: {self.socket_path}")

        try:
            while True:
                data, _ = server.recvfrom(1024)
                if data:
                    cmd = data.decode('utf-8')
                    self.process_command(cmd)
        except KeyboardInterrupt:
            print("\nShutting down leg controller...")
        finally:
            # Safely turn off servo PWM signals on exit
            self.pi.set_servo_pulsewidth(self.ud_pin, 0)
            self.pi.set_servo_pulsewidth(self.lr_pin, 0)
            self.pi.stop()
            server.close()
            if os.path.exists(self.socket_path):
                os.remove(self.socket_path)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Control a single 2-DOF soft robotic leg.")
    parser.add_argument('--ud-pin', type=int, required=True, help="GPIO pin for Up/Down servo")
    parser.add_argument('--lr-pin', type=int, required=True, help="GPIO pin for Left/Right servo")
    parser.add_argument('--socket', type=str, required=True, help="Unix socket path for IPC (e.g., /tmp/leg1.sock)")

    args = parser.parse_args()

    controller = LegController(ud_pin=args.ud_pin, lr_pin=args.lr_pin, socket_path=args.socket)
    controller.run()