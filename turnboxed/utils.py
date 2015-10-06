import os
import shutil
import tempfile
import json

from turnboxed import EXECUTABLE, DEBUG, LIB_ROOT, BASE_BOT_FILE

from rpython.translator.sandbox.sandlib import SimpleIOSandboxedProc
from rpython.translator.sandbox.sandlib import VirtualizedSocketProc
from rpython.translator.sandbox.vfs import Dir, RealDir, RealFile


class StdWriter(object):

    def __init__(self):
        self._lines = []

    def get_all_lines(self):
        return ''.join(self._lines)

    def write(self, data):
        self._lines.append(data)


class SandboxedCodeEval(VirtualizedSocketProc, SimpleIOSandboxedProc):
    argv0 = '/bin/pypy-c'
    virtual_cwd = '/tmp'
    virtual_env = {}
    virtual_console_isatty = True

    def __init__(self, script):
        self.executable = os.path.abspath(EXECUTABLE)
        self.sand_box_dir = os.path.abspath(os.path.dirname(script))
        self.stderr = StdWriter()

        self.debug = DEBUG
        self.script_path = os.path.join(self.virtual_cwd, os.path.basename(script))
        super(SandboxedCodeEval, self).__init__([self.argv0] + [self.script_path],
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

    def run_process(self):
        try:
            ret = self.interact(stderr=self.stderr)
            return ret, self.stderr.get_all_lines()
        finally:
            self.kill()

    def do_ll_os__ll_os_read(self, fd, size):
        if fd == 123456789:
            return json.dumps({"MSG": "QUIT"})
        else:
            return super(VirtualizedSocketProc, self).do_ll_os__ll_os_read(
            fd, size)

def evaluate_in_sandbox(code):
    new_temp_dir = tempfile.mkdtemp()
    script_path = os.path.abspath(os.path.join(new_temp_dir, 'script.py'))
    try:
        with open(script_path, 'w') as f:
            f.write(code)

        print "Script path: ", script_path
        p = SandboxedCodeEval(script_path)
        p.settimeout(3)
        ret, stderr = p.run_process()
        if ret != 0:
            ret = False
        else:
            ret = True
        print "Bot evaluation result: ", ret, stderr
        return ret, stderr
    except Exception, e:
        print "Error evaluating bot: ", e
        return False, str(e)
    finally:
        if os.path.exists(new_temp_dir):
            shutil.rmtree(new_temp_dir)