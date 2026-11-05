#!/usr/bin/env python3
import json
import os
import socket
import subprocess
import sys
import threading
import time

CONFIG_FILE = "config.json"
GAITS_FILE = "gaits/oneleg_gait.txt"
MASTER_SOCKET = "/tmp/robot_master.sock"
LEG_SOCKET_TEMPLATE = "/tmp/leg_{}.sock"

# Mechanical translation mapping
# Determines which physical servo directions map to the gait letters (f, b, F, B)
# L/R logic might be inverted for right-side legs depending on physical servo orientation
ACTION_MAP = {
    'L': { # Left side legs
        'f': ['D', 'L'], # Down, Forward (Assume L is forward for left legs)
        'b': ['D', 'R'], # Down, Backward
        'F': ['U', 'L'], # Up, Forward
        'B': ['U', 'R']  # Up, Backward
    },
    'R': { # Right side legs
        'f': ['D', 'R'], # Down, Forward (Assume R is forward for right legs)
        'b': ['D', 'L'], # Down, Backward
        'F': ['U', 'R'], # Up, Forward
        'B': ['U', 'L']  # Up, Backward
    }
}

class RobotMaster:
    def __init__(self):
        self.legs_config = self.load_config(CONFIG_FILE)
        self.gaits = self.load_gaits(GAITS_FILE)
        self.processes = []
        self.sockets = {}
        
        self.current_command = None
        self.last_command_time = time.time()
        self.idle_timeout = 1.0 # Seconds before returning to rest
        self.step_delay = 0.2   # Seconds between each line in a gait

    def load_config(self, filepath):
        with open(filepath, 'r') as f:
            return json.load(f)

    def load_gaits(self, filepath):
        gaits = {}
        current_gait = None
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'): continue
                
                if line.startswith('[') and line.endswith(']'):
                    current_gait = line[1:-1]
                    gaits[current_gait] = []
                elif current_gait:
                    # Split line into tokens, e.g., ["1Lb", "3Lb", "1RF"]
                    gaits[current_gait].append(line.split())
        return gaits

    def start_leg_controllers(self):
        print("Starting leg controllers...")
        for leg, pins in self.legs_config.items():
            sock_path = LEG_SOCKET_TEMPLATE.format(leg)
            cmd = [
                "python3", "leg_controller.py",
                "--ud-pin", str(pins['ud']),
                "--lr-pin", str(pins['lr']),
                "--socket", sock_path
            ]
            # Spawn child process
            p = subprocess.Popen(cmd)
            self.processes.append(p)
            
            # Create a socket client to talk to this leg
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.sockets[leg] = (sock, sock_path)
            
        time.sleep(1) # Give children time to initialize

    def send_to_leg(self, leg, commands):
        """Sends a list of commands (e.g., ['U', 'L']) to a specific leg."""
        if leg in self.sockets:
            sock, path = self.sockets[leg]
            for cmd in commands:
                try:
                    sock.sendto(cmd.encode('utf-8'), path)
                except FileNotFoundError:
                    print(f"Warning: Socket {path} not found.")

    def command_listener(self):
        """Runs in a background thread, listens for steering commands."""
        if os.path.exists(MASTER_SOCKET):
            os.remove(MASTER_SOCKET)
            
        server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        server.bind(MASTER_SOCKET)
        print(f"Master listening for steering commands on {MASTER_SOCKET}")
        
        while True:
            data, _ = server.recvfrom(1024)
            if data:
                cmd = data.decode('utf-8').strip().lower()
                if cmd in self.gaits or cmd == 'stop':
                    self.current_command = cmd if cmd != 'stop' else None
                    self.last_command_time = time.time()

    def rest_all_legs(self):
        """Centers horizontally and bottoms out vertically."""
        print("Idling: Moving all legs to rest position.")
        for leg in self.sockets:
            # Assuming 'REST' is handled in leg_controller.py to mean horizontal center, vertical bottom
            self.send_to_leg(leg, ['REST'])

    def run(self):
        self.start_leg_controllers()
        
        # Start IPC listener thread
        listener_thread = threading.Thread(target=self.command_listener, daemon=True)
        listener_thread.start()

        try:
            while True:
                # Check for idle timeout
                if self.current_command and (time.time() - self.last_command_time > self.idle_timeout):
                    self.current_command = None
                    self.rest_all_legs()

                if not self.current_command:
                    time.sleep(0.1)
                    continue

                # Execute Gait
                gait_sequence = self.gaits.get(self.current_command, [])
                for step in gait_sequence:
                    # Break loop immediately if command changes mid-gait
                    if not self.current_command or (time.time() - self.last_command_time > self.idle_timeout):
                        break
                        
                    # Execute all simultaneous leg movements in this line
                    for token in step:
                        # token looks like '1Lb' -> leg='1L', action='b'
                        leg = token[:2]   
                        action = token[2] 
                        side = leg[1]     # 'L' or 'R'
                        
                        if leg in self.sockets and side in ACTION_MAP and action in ACTION_MAP[side]:
                            cmds = ACTION_MAP[side][action]
                            self.send_to_leg(leg, cmds)
                            
                    time.sleep(self.step_delay)
                    
        except KeyboardInterrupt:
            print("\nMaster shutting down...")
        finally:
            self.cleanup()

    def cleanup(self):
        print("Terminating child processes...")
        for p in self.processes:
            p.terminate()
        for sock, path in self.sockets.values():
            sock.close()
        if os.path.exists(MASTER_SOCKET):
            os.remove(MASTER_SOCKET)

if __name__ == '__main__':
    master = RobotMaster()
    master.run()