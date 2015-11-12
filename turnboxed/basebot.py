import os
import json
import re
import traceback


class BaseBot(object):

    def __init__(self):
        self._turn_cookie = None

    def log_exception(self, excpt):
        os.write(123456789, json.dumps({"TURN_COOKIE": self._turn_cookie,
                                        "EXCEPTION": excpt.__class__.__name__ + " : " + str(excpt),
                                        "TRACEBACK": traceback.format_exc()}))

    def on_turn(self, msg):
        raise NotImplementedError

    def _get_turns(self):
        self._turn_cookie = None
        # Now wait for the turn
        msg = json.loads(os.read(123456789, 1024))
        if msg['MSG'] == "QUIT":
            return
        else:
            self._turn_cookie = msg['TURN_COOKIE']
            try:
                try:
                    feedback = msg["DATA"]
                except:
                    feedback = None

                turn_response = self.on_turn(feedback)
                os.write(123456789, json.dumps({"TURN_COOKIE": self._turn_cookie,
                                                "MSG": turn_response}))
            except Exception, e:
                self.log_exception(e)

            self._get_turns()


