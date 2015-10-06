import os
import httplib
import requests
import threading

from multiprocessing import Queue
import json
import shutil

from turnboxed import EXECUTABLE, LIB_ROOT, DEBUG, BASE_BOT_FILE

# PYPY_PATH = '/home/pguridi/src/pypy-2.6.1-src'
# EXECUTABLE = os.path.join(PYPY_PATH, 'pypy/goal/pypy-c')
# sys.path.insert(0, os.path.realpath(PYPY_PATH))

from rpython.translator.sandbox.sandlib import SimpleIOSandboxedProc
from rpython.translator.sandbox.sandlib import VirtualizedSocketProc
from rpython.translator.sandbox.vfs import Dir, RealDir, RealFile


class SandboxedPlayerController(VirtualizedSocketProc, SimpleIOSandboxedProc):
    argv0 = '/bin/pypy-c'
    virtual_cwd = '/tmp'
    virtual_env = {}
    virtual_console_isatty = True

    def __init__(self, player_id, player_script, bot_cookie, turn_event, connected_event, main_queue, std_out_queue):
        self.executable = os.path.abspath(EXECUTABLE)
        self.player_id = player_id
        self.bot_cookie = bot_cookie
        self.sand_box_dir = os.path.abspath(os.path.dirname(player_script))

        self.HOST = "localhost"
        self.PORT = 9999
        self.conn = None

        # Queue for IPC with game controller
        self.main_queue = main_queue
        # Queue for IPC with sandboxed code
        self.player_queue = Queue()

        self.std_out_queue = std_out_queue

        self.on_turn_event = turn_event
        self.on_connected_event = connected_event
        self.stop_event = None
        self.first_turn = False
        self.sandbox_connected = False

        self.debug = DEBUG
        self.turn_cookie = None
        self.script_path = os.path.join(self.virtual_cwd, "basebot.py")
        super(SandboxedPlayerController, self).__init__([self.argv0] + [self.script_path],
                                                executable=self.executable)

    def build_virtual_root(self):
        # build a virtual file system:
        # * can access its own executable
        # * can access the pure Python libraries
        # * can access the temporary usersession directory as /tmp
        exclude = ['.pyc', '.pyo']
        tmpdirnode = RealDir(self.sand_box_dir, exclude=exclude)
        libroot = str(LIB_ROOT)
        shutil.copy(BASE_BOT_FILE, self.sand_box_dir)

        return Dir({
            'bin': Dir({
                'pypy-c': RealFile(self.executable, mode=0111),
                'lib-python': RealDir(os.path.join(libroot, 'lib-python'),
                                      exclude=exclude),
                'lib_pypy': RealDir(os.path.join(libroot, 'lib_pypy'),
                                      exclude=exclude),
                }),
             'tmp': tmpdirnode,
             })

    def logg(self, msg):
        if not self.turn_cookie:
            turn_cookie = str(self.turn_cookie)
        else:
            turn_cookie = self.turn_cookie

        self.std_out_queue.put("[CONTROLLER][%s][%s] %s" % (self.bot_cookie, turn_cookie, str(msg)))

    def _main_loop(self):
        while True:
            msg = self.main_queue.get()
            if msg["MSG"] == "QUIT":
                self.player_queue.put({"MSG": "QUIT"})
                break
            elif msg['MSG'] == 'KILL':
                self.kill()
                break
            elif msg["MSG"] == "TURN":
                self.turn_cookie = msg["TURN_COOKIE"]
                self.player_queue.put({"MSG": "TURN",
                                       "TURN_COOKIE": msg["TURN_COOKIE"],
                                       "DATA": msg["DATA"]})

    def start_main_loop(self):
        main_loop_thread = threading.Thread(target=self._main_loop)
        # Exit the server thread when the main thread terminates
        main_loop_thread.daemon = True
        main_loop_thread.start()

    def connect_to_server(self):
        self.conn = httplib.HTTPConnection(self.HOST)

    def run_process(self):
        self.start_main_loop()
        try:
            self.interact()
        finally:
            self.kill()

    def send_to_game_controller(self, data):
        headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
        r = requests.post("http://%s:%s" % (self.HOST, self.PORT), data=json.dumps(data), headers=headers)

    #################################################################################
    # Custom communication methods and hacks for sandbox IPC.
    #################################################################################
    def do_ll_os__ll_os_read(self, fd, size):
        if fd == 123456789:
            if not self.sandbox_connected:
                self.logg("CONNECTED PLAYER CONTROLLER!")
                self.sandbox_connected = True
                self.on_connected_event.set()

            # Blocking method. Should wait until has a turn
            return json.dumps(self.player_queue.get())
        else:
            return super(VirtualizedSocketProc, self).do_ll_os__ll_os_read(
            fd, size)

    def do_ll_os__ll_os_write(self, fd, data):
        if fd == 123456789:
            if not self.sandbox_connected:
                return
            player_msg = json.loads(data)
            player_msg["BOT_COOKIE"] = self.bot_cookie

            if self.on_turn_event.is_set() and player_msg["TURN_COOKIE"] == self.turn_cookie:
                # Synchronous method.
                # Should connect to the Game Controller to evaluate action
                self.send_to_game_controller(player_msg)
                return 0
            else:
                self.logg("BAD TURN. %s" % player_msg)
                return 0
        else:
            return super(VirtualizedSocketProc, self).do_ll_os__ll_os_write(
                fd, data)
    #################################################################################