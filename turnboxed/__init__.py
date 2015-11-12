import os
import sys

if 'PYPY_PATH' not in os.environ.keys():
    PYPY_PATH = '/opt/pypy-4.0.0-src'
else:
    PYPY_PATH = os.environ['PYPY_SOURCE_PATH']

EXECUTABLE = os.path.join(PYPY_PATH, 'pypy/goal/pypy-c')
sys.path.insert(0, os.path.realpath(PYPY_PATH))


DEBUG = False

import pypy
LIB_ROOT = os.path.dirname(os.path.dirname(pypy.__file__))

from . import basebot

current_dir = os.path.split(basebot.__file__)[0]
BASE_BOT_FILE = os.path.abspath(os.path.join(current_dir, "basebot.py"))
GAME_BOT_DIR = os.environ.get('GAME_BOT_DIR', current_dir)
GAME_BOT_FILE = os.path.abspath(os.path.join(GAME_BOT_DIR, "gamebot.py"))
