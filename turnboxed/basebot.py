import os
import json


class BaseBot(object):

    def __init__(self):
        self._exit = False
        self._turn_cookie = None
        self._actions = []
        self._get_turns()

    def log_exception(self, excpt):
        os.write(123456789, json.dumps({"TURN_COOKIE": self._turn_cookie,
                                        "EXCEPTION": str(excpt)}))

    def on_turn(self, msg):
        raise NotImplementedError

    def attack(self, victim):
        self._actions.append('%'.join(["ATTACK", victim]))

    def _get_turns(self):
        self._turn_cookie = None
        # Now wait for the turn
        msg = json.loads(os.read(123456789, 1024))
        if msg['MSG'] == "QUIT":
            return
        else:
            self._turn_cookie = msg['TURN_COOKIE']
            try:
                turn_response = self.on_turn(msg)
                os.write(123456789, json.dumps({"TURN_COOKIE": self._turn_cookie,
                                                "MSG": turn_response}))
            except Exception, e:
                self.log_exception(e)

            self._get_turns()