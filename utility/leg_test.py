import time
import pygame
from gpiozero import Servo

# 1. Initialize Pygame & Window
pygame.init()
pygame.joystick.init()

# Setup Display Window
WIDTH, HEIGHT = 400, 400
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Gamepad Servo Visualizer")

# Colors and Geometry
BG_COLOR = (30, 30, 30)
CIRCLE_COLOR = (200, 200, 200)
DOT_COLOR = (255, 50, 50)
CENTER = (WIDTH // 2, HEIGHT // 2)
RADIUS = 150

# 2. Detect the Gamepad
if pygame.joystick.get_count() == 0:
    print("No gamepad detected! Please plug one in and restart.")
    pygame.quit()
    exit()

joystick = pygame.joystick.Joystick(0)
joystick.init()
print(f"Connected to: {joystick.get_name()}")

# 3. Setup Servos (Uses modern lgpio backend automatically)
# MG90S typically uses 0.5ms to 2.5ms for the full 180-degree sweep.
# If the motors buzz or grind at the extreme edges, change 0.5 to 0.6 and 2.5 to 2.4.
servo1 = Servo(18, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
servo2 = Servo(13, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)

DEADZONE = 0.1 
running = True

print("Running... Move the left thumbstick. Close window or press Ctrl+C to stop.")

try:
    while running:
        # 4. Handle UI Events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
        
        # 5. Read and round Joystick Axes to 2 decimal places to kill sensor noise
        x_axis = round(joystick.get_axis(0), 2)
        y_axis = round(joystick.get_axis(1), 2)
        
        # Apply deadzone to prevent drift when thumbstick is resting
        if abs(x_axis) < DEADZONE: x_axis = 0.0
        if abs(y_axis) < DEADZONE: y_axis = 0.0
        
        # 6. Update Servos (Values must be between -1.0 and 1.0)
        servo1.value = x_axis
        servo2.value = -y_axis  # Invert Y for standard UP = MAX behavior
        
        # 7. Draw the Visualization
        screen.fill(BG_COLOR)
        
        # Draw the boundary circle (width=2 for outline)
        pygame.draw.circle(screen, CIRCLE_COLOR, CENTER, RADIUS, 2)
        
        # Calculate dot position on screen
        dot_x = int(CENTER[0] + (x_axis * RADIUS))
        dot_y = int(CENTER[1] + (y_axis * RADIUS))
        
        # Draw the joystick dot
        pygame.draw.circle(screen, DOT_COLOR, (dot_x, dot_y), 10)
        
        # Refresh screen
        pygame.display.flip()
        
        # Limit framerate to ~60 FPS
        time.sleep(1/60)
        
except KeyboardInterrupt:
    print("\nExiting and turning off servo signals...")
finally:
    # Detach stops the PWM signal so motors stop holding position and generating heat
    servo1.detach()
    servo2.detach()
    pygame.quit()
