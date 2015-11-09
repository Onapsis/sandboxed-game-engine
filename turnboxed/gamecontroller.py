import os
import time
from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from SocketServer import ThreadingMixIn
import threading
import uuid
import json
from multiprocessing import Queue, Event, Process

from .playercontroller import SandboxedPlayerController
from .exceptions import GameFinishedException, GameLogicException, TimeoutException


def get_cookie():
    return uuid.uuid4().hex[0:8]


class GameControllerHTTPRequestHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        return

    def do_POST(self):
        content_len = int(self.headers.getheader('content-length'))
        post_body = self.rfile.read(content_len)
        # Parse content
        data = json.loads(post_body)
        bot_cookie = data["BOT_COOKIE"]

        # Handle the bot controller request
        ret = self.server.game_controller.handle_player_request(data, bot_cookie)

        if ret == 0:
            self.send_response(200)
        else:
            self.send_response(501)

        self.send_header('Content-type', 'application/json')
        self.end_headers()

        self.wfile.write(json.dumps(ret))
        return

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


class BaseGameController:

    def __init__(self):
        self._server = None
        self._server_thread = None
        self.server_host = "localhost"
        self.server_port = 9999
        self.rounds = 100
        self.current_round = 0
        self.players = {}
        self.finish_game_event = Event()
        self._exception = None

        self._bot_in_turn = None
        self.turns_queue = Queue()
        self.std_out_queue = Queue()
        self.stop_event = Event()

    def log_msg(self, msg):
        self.std_out_queue.put(msg)

    def handle_player_request(self, data, bot_cookie):
        if self.players[bot_cookie]["turn_event"].is_set() and self._bot_in_turn == bot_cookie:
            try:
                ret = self.evaluate_turn(data, bot_cookie)
                return ret
            except Exception, e:
                # Error in game logic
                self.log_msg("GAME LOGIC ERROR: " + str(e))
                self.stop()
                self._exception = (GameLogicException, str(e))
            finally:
                self.players[bot_cookie]["turn_event"].clear()
                self._bot_in_turn = None
        else:
            # Wrong turn!
            self.log_msg("WRONG TURN FROM BOT %s" % bot_cookie)
            return -1

    def evaluate_turn(self, player, request):
        raise NotImplementedError

    def _start_http_server(self):
        self._server = ThreadedHTTPServer((self.server_host, self.server_port), GameControllerHTTPRequestHandler)
        self._server.game_controller = self
        self.log_msg("Starting http server server..")
        self._server_thread = threading.Thread(target=self._server.serve_forever)
        # Exit the server thread when the main thread terminates
        self._server_thread.daemon = True
        self._server_thread.start()
        self.log_msg("Server loop running in thread: %s PORT: %s" % (self._server_thread.name, self.server_port))

    def add_player(self, player_id, player_script):
        bot_cookie = get_cookie()
        turn_event = Event()
        connected_event = Event()
        main_queue = Queue()
        self.players[bot_cookie] = {"player_id": player_id,
                                    "bot_cookie": bot_cookie,
                                    "player_script": player_script,
                                    "turn_event": turn_event,
                                    "connected_event": connected_event,
                                    "main_queue": main_queue}

    def run_player_process(self, player_d, p_k):
        p = SandboxedPlayerController(player_d["player_id"], os.path.abspath(player_d["player_script"]),
                                    player_d["bot_cookie"], player_d["turn_event"],
                                    player_d["connected_event"], player_d["main_queue"],
                                    self.std_out_queue)
        p.run_process()

    def run_stdout_thread(self):
        def _print_queue():
            while True:
                while not self.std_out_queue.empty():
                    print(self.std_out_queue.get())
                if self.stop_event.is_set():
                    break
                time.sleep(0.05)
        stdout_thread = threading.Thread(target=_print_queue)
        # Exit the server thread when the main thread terminates
        stdout_thread.daemon = True
        stdout_thread.start()

    def get_turn_data(self, bot_cookie):
        return None

    def stop(self):
        self.finish_game_event.set()

    def raise_if_stopped(self):
        if self.finish_game_event.is_set():
            raise GameFinishedException

    def _start_rounds(self):
        self.log_msg("Starting rounds")
        try:
            for i in range(0, self.rounds):
                self.current_round = i
                self.raise_if_stopped()
                self.log_msg("\n\nStarting round %s\n" % str(i))

                for p_k in self.players.keys():
                    self.raise_if_stopped()
                    turn_cookie = get_cookie()
                    self.log_msg("\n===== STARTED TURN %s FOR BOT %s" % (turn_cookie, self.players[p_k]["bot_cookie"]))
                    self._bot_in_turn = p_k
                    self.players[p_k]["turn_event"].set()
                    try:
                        turn_data = {"MSG": "TURN",
                                     "DATA": self.get_turn_data(p_k),
                                     "TURN_COOKIE": turn_cookie}

                        self.players[p_k]["main_queue"].put(json.dumps(turn_data))
                    except Exception, e:
                        raise GameLogicException("Turn data error %s" % str(e))
                    # Wait for the player to finish the turn...
                    max_wait = 2
                    while self.players[p_k]["turn_event"].is_set():
                        if max_wait < 1:
                            self.players[p_k]["main_queue"].put(json.dumps({"MSG": "KILL"}))
                            raise GameFinishedException("Player %s turn timeout." % self.players[p_k]['player_id'])
                        else:
                            sleep_time = 0.02
                            max_wait -= sleep_time
                            # turn based timeout check could go here
                            time.sleep(sleep_time)
                    self._bot_in_turn = None
                    self.log_msg("===== ENDED TURN %s FOR BOT %s" % (turn_cookie, self.players[p_k]["bot_cookie"]))
        except GameFinishedException, e:
            self.log_msg("FINISHED GAME")
        except GameLogicException, e:
            self.log_msg("GAME ERROR")
            self._exception = (GameLogicException, str(e))

    def run(self):
        self._start_http_server()
        self.run_stdout_thread()

        startup_okay = True
        # Start all the sandbox processes
        for p_k in self.players.keys():
            self.log_msg("Starting player..")
            p = Process(target=self.run_player_process, args=(self.players[p_k], p_k))
            p.start()

            # Wait for the sandbox process to connect to the controller.
            max_wait = 3
            connected = True
            while not self.players[p_k]["connected_event"].is_set():
                if max_wait < 1 or not p.is_alive():
                    connected = False
                    break
                sleep_time = 0.05
                max_wait -= sleep_time
                time.sleep(sleep_time)
            if connected:
                self.log_msg("Player %s connected" % self.players[p_k]["bot_cookie"])
            else:
                # player couldn't connect
                startup_okay = False
                err_msg = "Player %s didn't connect in time." % self.players[p_k]['player_id']
                self.log_msg(err_msg)
                self.players[p_k]["main_queue"].put(json.dumps({"MSG": "KILL"}))
                self._exception = (TimeoutException, err_msg)
                break

        if startup_okay:
            self._start_rounds()
        else:
            self.stop()

        for p_k in self.players.keys():
            self.players[p_k]["main_queue"].put(json.dumps({"MSG": "QUIT"}))

        self.log_msg("\nCLOSING..")
        # Exit

        self.log_msg("Shutting down http server...")
        time.sleep(2)
        self._server.shutdown()
        self.stop_event.set()

        if self._exception:
            raise self._exception[0](self._exception[1])
