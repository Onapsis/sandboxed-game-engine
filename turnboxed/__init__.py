import os
import sys

PYPY_PATH = '/home/pguridi/src/pypy-2.6.1-src'
EXECUTABLE = os.path.join(PYPY_PATH, 'pypy/goal/pypy-c')
DEBUG = False

sys.path.insert(0, os.path.realpath(PYPY_PATH))

import pypy
LIB_ROOT = os.path.dirname(os.path.dirname(pypy.__file__))

from . import basebot
current_dir = os.path.split(basebot.__file__)[0]
BASE_BOT_FILE = os.path.abspath(os.path.join(current_dir, "basebot.py"))