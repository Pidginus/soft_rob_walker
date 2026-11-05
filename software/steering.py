#!/usr/bin/env python3
import curses
import socket
import sys
import time

# Address of the Unix socket managed by master.py
MASTER_SOCKET = "/tmp/robot_master.sock"

# Map arrow key constants to gait command strings expected by master.py
KEY_COMMAND_MAP = {
    curses.KEY_UP: "forward",
    curses.KEY_DOWN: "backward",
    curses.KEY_LEFT: "left",
    curses.KEY_RIGHT: "right",
}


def send_command(sock: socket.socket, command: str):
    """Sends a gait command string to the master process via Unix socket."""
    try:
        sock.sendto(command.encode("utf-8"), MASTER_SOCKET)
    except FileNotFoundError:
        pass  # Master script is not running or socket file was removed
    except Exception as e:
        pass


def main(stdscr):
    # Setup curses UI
    curses.curs_set(0)  # Hide mouse/blinking cursor
    stdscr.nodelay(True)  # Make getch() non-blocking
    stdscr.timeout(100)  # Wait max 100ms for input before looping

    # Create IPC client socket
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

    stdscr.clear()
    stdscr.addstr(0, 0, "=== 6-LEGGED ROBOT STEERING CONTROLLER ===")
    stdscr.addstr(2, 0, "Use ARROW KEYS to steer:")
    stdscr.addstr(3, 2, "UP    : Move Forward")
    stdscr.addstr(4, 2, "DOWN  : Move Backward")
    stdscr.addstr(5, 2, "LEFT  : Rotate Left")
    stdscr.addstr(6, 2, "RIGHT : Rotate Right")
    stdscr.addstr(8, 0, "Press 'q' or ESC to exit.")
    stdscr.addstr(10, 0, "Status: ACTIVE")
    stdscr.refresh()

    last_sent_cmd = None
    heartbeat_interval = 0.2  # Resend active key command every 200ms
    last_send_time = 0

    try:
        while True:
            key = stdscr.getch()

            # Exit check
            if key == ord("q") or key == ord("Q") or key == 27:  # 27 is ESC key
                send_command(client_socket, "stop")
                break

            current_time = time.time()

            if key in KEY_COMMAND_MAP:
                cmd = KEY_COMMAND_MAP[key]
                # Send immediately if key changed or heartbeat interval reached
                if (
                    cmd != last_sent_cmd
                    or (current_time - last_send_time) > heartbeat_interval
                ):
                    send_command(client_socket, cmd)
                    last_sent_cmd = cmd
                    last_send_time = current_time

                # Display active status
                stdscr.addstr(
                    12,
                    0,
                    f"Sending: {cmd.upper():<15}",
                    curses.A_BOLD | curses.A_REVERSE,
                )
            elif key == -1:
                # No key pressed in this cycle
                if (
                    last_sent_cmd
                    and (current_time - last_send_time) > heartbeat_interval
                ):
                    stdscr.addstr(12, 0, "Sending: IDLE / REST          ")
                    last_sent_cmd = None

            stdscr.refresh()

    finally:
        client_socket.close()


if __name__ == "__main__":
    try:
        curses.wrapper(main)
    except KeyboardInterrupt:
        sys.exit(0)
