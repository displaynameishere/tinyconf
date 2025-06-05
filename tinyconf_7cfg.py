# this is a modified version of the .7cfg parser 
# from recon7 (https://github.com/fdisplaynameishere/recon7). 
# it extracts theme data, so you can use the same configs for both :)

import re
from typing import Union

class Config:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.data = {
            "theme": {},
            "numbers" : {}
        }
        self._parse_config()

    def _parse_config(self):
        with open(self.filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("//"):
                    continue

                if line.startswith("theme:"):
                    self._parse_theme(line)
                elif line.startswith("number:"):
                    self._parse_number(line)
                else:
                    continue
    def _parse_number(self, line: str):
        match = re.match(r'num:(\w+)\s+(\d+)', line)
        if match:
            key, value = match.groups()
            self.data["numbers"][key] = int(value)

    def _parse_theme(self, line: str):
        match = re.match(r'theme:(\w+)\s+(#[0-9a-fA-F]{6})', line)
        if match:
            key, value = match.groups()
            self.data["theme"][key] = value

    # accesors
    def get_number(self, key: str) -> Union[int, None]:
        return self.data["numbers"].get(key)

    def get(self, key: str) -> Union[str, int, None]:
        """
        Allows access via 'theme:bg' or 'number:delay' style keys.
        """
        if ':' not in key:
            return None
        section, subkey = key.split(':', 1)
        return self.data.get(section, {}).get(subkey)
    def all_numbers(self):
        return self.data["numbers"]

    def all_theme(self):
        return self.data["theme"]