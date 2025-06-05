import curses
import argparse
import os
import sys
import re
import termios
import tty

class TinyconfEditor:
    version = "0.1.0"

    def __init__(self, stdscr, fg_rgb=(255, 255, 255), bg_rgb=(0, 0, 0), status_rgb=(100, 100, 100), filepath=None):
        self.stdscr = stdscr
        self.buffer = [""]
        self.cursor_y = 0
        self.cursor_x = 0
        self.scroll_offset = 0
        self.filepath = filepath
        self.status = "EXEC MODE: type /q to quit, /s to save"
        self.status_timer = 0
        self.unsaved = False
        self.command_mode = False
        self.command_input = ""
        self.slash_prefix = False

        if self.filepath and os.path.exists(self.filepath):
            with open(self.filepath, 'r') as f:
                self.buffer = f.read().splitlines() or [""]

        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        curses.mouseinterval(0)

        curses.start_color()
        curses.use_default_colors()
        fg_code, bg_code, st_code = 250, 251, 252

        def rgb(c): return tuple(int((v / 255) * 1000) for v in c)

        curses.init_color(fg_code, *rgb(fg_rgb))
        curses.init_color(bg_code, *rgb(bg_rgb))
        curses.init_color(st_code, *rgb(status_rgb))

        curses.init_pair(1, fg_code, bg_code)
        curses.init_pair(2, fg_code, st_code)

        self.color = curses.color_pair(1)
        self.status_color = curses.color_pair(2)

        self.main()

    def draw(self):
        h, w = self.stdscr.getmaxyx()
        visible_height = h - 1

        self.scroll_offset = min(self.scroll_offset, max(0, len(self.buffer) - visible_height))
        self.cursor_y = max(0, min(self.cursor_y, len(self.buffer) - 1))

        if self.cursor_y < self.scroll_offset:
            self.scroll_offset = self.cursor_y
        elif self.cursor_y >= self.scroll_offset + visible_height:
            self.scroll_offset = self.cursor_y - visible_height + 1

        for i in range(h):
            try:
                self.stdscr.addstr(i, 0, " " * w, self.color)
            except curses.error:
                pass

        for i in range(visible_height):
            line_index = self.scroll_offset + i
            if line_index >= len(self.buffer):
                break
            line = self.buffer[line_index]
            line_num = f"{line_index + 1:4} "
            try:
                self.stdscr.addstr(i, 0, line_num, self.color)
                self.stdscr.addstr(i, len(line_num), line[:w - len(line_num)], self.color)
            except curses.error:
                pass

        display_y = self.cursor_y - self.scroll_offset
        self.cursor_x = min(self.cursor_x, len(self.buffer[self.cursor_y]))
        try:
            self.stdscr.move(display_y, self.cursor_x + 5)
        except curses.error:
            pass

        try:
            status_line = f"/{self.command_input}" if self.command_mode else self.status
            clipped_status = (status_line + " " * w)[:w]
            self.stdscr.addstr(h - 1, 0, clipped_status, self.status_color)
        except curses.error:
            pass
        self.stdscr.refresh()

    def insert(self, ch):
        line = self.buffer[self.cursor_y]
        self.buffer[self.cursor_y] = line[:self.cursor_x] + ch + line[self.cursor_x:]
        self.cursor_x += 1
        self.unsaved = True

    def backspace(self):
        if self.cursor_x > 0:
            line = self.buffer[self.cursor_y]
            self.buffer[self.cursor_y] = line[:self.cursor_x - 1] + line[self.cursor_x:]
            self.cursor_x -= 1
        elif self.cursor_y > 0:
            prev = self.buffer[self.cursor_y - 1]
            self.cursor_x = len(prev)
            self.buffer[self.cursor_y - 1] += self.buffer[self.cursor_y]
            self.buffer.pop(self.cursor_y)
            self.cursor_y -= 1
        self.unsaved = True

    def newline(self):
        line = self.buffer[self.cursor_y]
        self.buffer[self.cursor_y] = line[:self.cursor_x]
        self.buffer.insert(self.cursor_y + 1, line[self.cursor_x:])
        self.cursor_y += 1
        self.cursor_x = 0
        self.unsaved = True

    def move_cursor(self, key):
        if key == curses.KEY_UP and self.cursor_y > 0:
            self.cursor_y -= 1
        elif key == curses.KEY_DOWN and self.cursor_y < len(self.buffer) - 1:
            self.cursor_y += 1
        elif key == curses.KEY_LEFT:
            if self.cursor_x > 0:
                self.cursor_x -= 1
            elif self.cursor_y > 0:
                self.cursor_y -= 1
                self.cursor_x = len(self.buffer[self.cursor_y])
        elif key == curses.KEY_RIGHT:
            if self.cursor_x < len(self.buffer[self.cursor_y]):
                self.cursor_x += 1
            elif self.cursor_y < len(self.buffer) - 1:
                self.cursor_y += 1
                self.cursor_x = 0
        self.cursor_x = min(self.cursor_x, len(self.buffer[self.cursor_y]))

    def save_file(self):
        if self.filepath:
            with open(self.filepath, 'w') as f:
                f.write("\n".join(self.buffer))
            self.unsaved = False
            self.status = "File saved."
            self.status_timer = 20

    def prompt_save(self):
        self.status = "Save before quitting? (y/N/esc)"
        self.draw()
        while True:
            key = self.stdscr.getch()
            if key == 27:
                self.status = "Canceled."
                self.status_timer = 20
                return False
            elif key in (ord('y'), ord('Y')):
                self.save_file()
                return True
            elif key in (ord('n'), ord('N')):
                return True

    def handle_command(self):
        cmd = self.command_input.strip()
        if cmd == "/":
            self.insert("/")
        elif cmd == "q":
            if not self.unsaved or self.prompt_save():
                return False
        elif cmd == "s":
            self.save_file()
        self.command_input = ""
        self.command_mode = False
        return True

    def main(self):
        curses.curs_set(1)
        self.stdscr.keypad(True)
        while True:
            self.draw()
            if self.status_timer > 0:
                self.status_timer -= 1
                if self.status_timer == 0:
                    self.status = "COMMAND MODE: type /q to quit, /s to save"
            key = self.stdscr.getch()
            if self.command_mode:
                if key in (10, 13):  # Enter
                    if not self.handle_command():
                        break
                elif key in (27,):  # ESC
                    self.command_input = ""
                    self.command_mode = False
                elif key in (curses.KEY_BACKSPACE, 127):
                    self.command_input = self.command_input[:-1]
                elif 0 <= key < 256:
                    self.command_input += chr(key)
                continue

            if key == ord("/"):
                self.command_mode = True
                self.command_input = ""
            elif key in (curses.KEY_BACKSPACE, 127):
                self.backspace()
            elif key == curses.KEY_ENTER or key == 10:
                self.newline()
            elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT):
                self.move_cursor(key)
            elif key == curses.KEY_MOUSE:
                _, mx, my, _, bstate = curses.getmouse()
                if my < self.stdscr.getmaxyx()[0] - 1:
                    line_idx = self.scroll_offset + my
                    if 0 <= line_idx < len(self.buffer):
                        self.cursor_y = line_idx
                        self.cursor_x = max(0, min(mx - 5, len(self.buffer[self.cursor_y])))
            elif 0 <= key < 256:
                self.insert(chr(key))
        if self.filepath and self.unsaved:
            self.save_file()

def hex_to_rgb(hex_str):
    if isinstance(hex_str, tuple):
        return hex_str
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def disable_flow_control():
    if sys.stdin.isatty():
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[3] = attrs[3] & ~(termios.IXON | termios.IXOFF | termios.IXANY)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

def run_tinyconf():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", help="File to open")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    args = parser.parse_args()

    if args.version:
        print(TinyconfEditor.version)
        sys.exit(0)

    filepath = args.file
    if filepath and not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            f.write("")

    disable_flow_control()

    curses.wrapper(lambda stdscr: TinyconfEditor(stdscr, filepath=filepath))

if __name__ == "__main__":
    run_tinyconf()
