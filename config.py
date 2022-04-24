import json
import os


class config():
    def __init__(self, filename="config.json"):
        self.file = filename
        if not os.path.exists(filename):
            with open(self.file, 'w') as f:
                json.dump({}, f)
        with open(self.file, 'r') as f:
            self.data = json.loads(f.read(-1))

    def save(self):
        with open(self.file, 'w') as f:
            json.dump(self.data, f)
