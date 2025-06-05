import curses
import argparse
import os
import sys
import termios
from ttiny.ttiny_7cfg import Config

CONFIG_PATH = os.path.expanduser("~/.ttiny")

def ensure_config_exists():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            f.write(
                "theme:bg #000000\n"
                "theme:fg #ffffff\n"
                "theme:status #666666\n"
            )

def hex_to_rgb(hex_str):
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def disable_flow_control():
    if sys.stdin.isatty():
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[3] = attrs[3] & ~(termios.IXON | termios.IXOFF | termios.IXANY)
        termios.tcsetattr(fd, termios.TCSANOW, attrs)

class TtinyEditor:
    version = "0.1.0"

    def __init__(self, stdscr, filepath=None):
        self.stdscr = stdscr
        self.filepath = filepath
        self.buffer = [""]
        self.cursor_y = 0
        self.cursor_x = 0
        self.scroll_offset = 0
        self.status = "EXEC MODE: type /q to quit, /s to save, // for literal slash"
        self.status_timer = 0
        self.unsaved = False
        self.command_mode = False
        self.command_input = ""
        self.quit_confirm = False

        if filepath and os.path.exists(filepath):
            with open(filepath, 'r') as f:
                self.buffer = f.read().splitlines() or [""]

        config = Config(CONFIG_PATH)
        fg_rgb = hex_to_rgb(config.get("theme:fg") or "#ffffff")
        bg_rgb = hex_to_rgb(config.get("theme:bg") or "#000000")
        status_rgb = hex_to_rgb(config.get("theme:statusbar") or "#666666")

        curses.start_color()
        curses.use_default_colors()
        fg_code, bg_code, st_code = 250, 251, 252
        to_1000 = lambda rgb: tuple(int((v / 255) * 1000) for v in rgb)

        curses.init_color(fg_code, *to_1000(fg_rgb))
        curses.init_color(bg_code, *to_1000(bg_rgb))
        curses.init_color(st_code, *to_1000(status_rgb))

        curses.init_pair(1, fg_code, bg_code)
        curses.init_pair(2, fg_code, st_code)

        self.color = curses.color_pair(1)
        self.status_color = curses.color_pair(2)

        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        curses.mouseinterval(0)

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
        try:
            for i in range(h):
                self.stdscr.addstr(i, 0, " " * w, self.color)
        except curses.error:
            pass

        for i in range(visible_height):
            line_index = self.scroll_offset + i
            if line_index >= len(self.buffer):
                break
            line = self.buffer[line_index]
            line_num = f"{line_index + 1:4} "
            self.stdscr.addstr(i, 0, line_num, self.color)

            if line_index == self.cursor_y:
                cx = min(self.cursor_x, len(line))
                before = line[:cx]
                cur = line[cx:cx+1] or " "
                after = line[cx+1:]

                self.stdscr.addstr(i, 5, before, self.color)
                self.stdscr.addstr(i, 5 + len(before), cur, self.color | curses.A_UNDERLINE)
                self.stdscr.addstr(i, 5 + len(before) + 1, after, self.color)
            else:
                self.stdscr.addstr(i, 5, line[:w - 5], self.color)

        try:
            self.stdscr.addstr(h - 1, 0, ("/" + self.command_input if self.command_mode else self.status).ljust(w), self.status_color)
        except curses.error:
            pass

        self.stdscr.refresh()

    def insert(self, ch):
        line = self.buffer[self.cursor_y]
        self.buffer[self.cursor_y] = line[:self.cursor_x] + ch + line[self.cursor_x:]
        self.cursor_x += 1
        self.unsaved = True
        self.quit_confirm = False
        self.status = "EXEC MODE: type /q to quit, /s to save, // for literal slash"

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
        self.quit_confirm = False
        self.status = "EXEC MODE: type /q to quit, /s to save, // for literal slash"

    def newline(self):
        line = self.buffer[self.cursor_y]
        self.buffer[self.cursor_y] = line[:self.cursor_x]
        self.buffer.insert(self.cursor_y + 1, line[self.cursor_x:])
        self.cursor_y += 1
        self.cursor_x = 0
        self.unsaved = True
        self.quit_confirm = False
        self.status = "EXEC MODE: type /q to quit, /s to save, // for literal slash"

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
            if self.unsaved and not self.quit_confirm:
                self.quit_confirm = True
                self.status = "Unsaved changes — type /q again to quit without saving"
                self.status_timer = 30
            else:
                sys.exit(0)
        elif cmd == "s":
            self.save_file()
        self.command_input = ""
        self.command_mode = False
        return True

    def main(self):
        curses.curs_set(0)
        self.stdscr.keypad(True)
        while True:
            self.draw()
            if self.status_timer > 0:
                self.status_timer -= 1
            if self.status_timer == 0:
                self.status = "EXEC MODE: type /q to quit, /s to save, // for literal slash"
                self.quit_confirm = False
            key = self.stdscr.getch()
            if self.command_mode:
                if key in (10, 13):
                    if not self.handle_command():
                        break
                elif key == 27:
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
            elif key in (10, curses.KEY_ENTER):
                self.newline()
            elif key in (curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT):
                self.move_cursor(key)
            elif key == curses.KEY_MOUSE:
                _, mx, my, _, _ = curses.getmouse()
                if my < self.stdscr.getmaxyx()[0] - 1:
                    self.cursor_y = min(len(self.buffer) - 1, self.scroll_offset + my)
                    self.cursor_x = max(0, min(mx - 5, len(self.buffer[self.cursor_y])))
            elif 0 <= key < 256:
                self.insert(chr(key))
        if self.filepath and self.unsaved:
            self.save_file()

def run_ttiny():
    parser = argparse.ArgumentParser()
    parser.add_argument("file", nargs="?", help="File to open")
    parser.add_argument("-v", "--version", action="store_true", help="Show version")
    args, unknown = parser.parse_known_args()

    if args.version:
        print("""
████████ ████████ ██ ███    ██ ██    ██ 
   ██       ██    ██ ████   ██  ██  ██  
   ██       ██    ██ ██ ██  ██   ████   
   ██       ██    ██ ██  ██ ██    ██    
   ██       ██    ██ ██   ████    ██    
              """)
        print("version", TtinyEditor.version)
        sys.exit(0)

    if unknown:
        print(f"usage: ttiny [-h] [-v] [file]\nUnrecognized argument(s): {unknown}")
        exit()

    ensure_config_exists()
    disable_flow_control()

    curses.wrapper(lambda stdscr: TtinyEditor(stdscr, filepath=args.file))

if __name__ == "__main__":
    run_ttiny()
