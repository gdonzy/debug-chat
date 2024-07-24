import re
import epdb
import inspect
import time

from .debug_apps import create_debug_app
from .utils import get_py_lno_vars_map

class DebugEntry(object):
    
    @classmethod
    def init_app(cls, app):
        debug_app = create_debug_app(app)
        debug_app.register_break_entry()
        
class DebugClient(object):
    bt_file_lineno_pattern = re.compile(r"^(.+)\((\d+)\)")
    
    def __init__(self, host, port, include_dirs=None, exclude_dirs=None):
        self.host = host
        self.port = port
        self.client = self.conn()
        self.py_lineno_variables = {}
        self.include_dirs = include_dirs
        self.exclude_dirs = exclude_dirs
        # bt:back trace info, fn:filename, lno:line no, entry_fn: entry filename
        self.bt, self.fn, self.lno, self.entry_fn = [], None, None, None
        self.preproc()
    
    def conn(self):
        client = epdb.connect(host=self.host, port=self.port)
        return client
    
    def preproc(self):
        stack_lines = self.exec_cmd_resp(b'bt\n')
        if 'before_request_proc' in ''.join(stack_lines[-5:]):
            # get route
            route_lines = self.exec_cmd_resp(b'pp f"route={route}"\n')
            for l in route_lines:
                if 'route=' in l:
                    route = (l.replace('\'', '').replace('route=', '')).strip()
                    break
            route = route[:-1] if route.endswith('/') else route
            # get method
            method_lines = self.exec_cmd_resp(b'pp f"method={request.method}"')
            for l in method_lines:
                if 'method=' in l:
                    method = (l.replace('\'', '').replace('method=', '')).strip()
                    break
            method = method.lower()
    
            fn, lno = None, None
            for rule in app.url_map.iter_rules():
                url = rule.rule[:-1] if rule.rule.endswith('/') else rule.rule
                if url == route:
                    view_class = app.view_functions[rule.endpoint].view_class
                    view_method = getattr(view_class, method)
                    fn = inspect.getfile(view_class)
                    codes, lno = inspect.getsourcelines(view_method)
                    for idx, l in enumerate(codes):
                        if (l.strip()).startswith('def') and f'{method}(self' in l:
                            lno += idx
                            break
                    break
                
            self.run(end_condition=lambda debug_handler: debug_handler.fn == fn and debug_handler.lno == lno)
                
    
    def send_cmd(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode('ascii')
        if not cmd.endswith(b'\n'):
            cmd += b'\n'
        self.client.write(cmd)
        
    def get_resp(self):
        resp_bytes = b''
        for i in range(3):
            part_bytes = self.client.read_very_eager()
            if part_bytes:
                resp_bytes += part_bytes
            else:
                time.sleep(0.01)
        resp = resp_bytes.decode('utf-8')
        return resp
    
    def exec_cmd_resp(self, cmd, split_to_lines=True):
        self.send_cmd(cmd)
        resp = self.get_resp()
        if split_to_lines:
            return resp.split('\n')
        else:
            return resp
        
    def get_curr_filename_lineno(self):
        lines = self.exec_cmd_resp(b'bt\n')
        fn, lno = None, None
        for l in lines[:-5:-1]:
            if self.bt_file_lineno_pattern.match(l):
                match = self.bt_file_lineno_pattern.search(l)
                fn = match.group(1)
                try:
                    lno = int(match.group(2))
                except Exception as e:
                    print(e)
                break
        return fn, lno
    
    def step_recursive(self, log_info, end_condition):
        print(self.bt[-3:])
        if end_condition(self):
            print(1)
            return

        if (not log_info) or (log_info.get('filename') != self.fn or log_info.get('') != self.lno):
            log_info = {
                'filename': self.fn,
                'lineno': self.lno,
                'before_exec': {},
                'after_exec': {},
            }
        
        self.exec_cmd_resp(b's\n')
        self.bt = self.exec_cmd_resp(b'bt\n')
        self.fn, self.lno = self.get_curr_filename_lineno()
        # 特殊情况：代码跟踪位置不在include_dirs，或者在exclude_dirs中，此时要返回后再执行后续操作
        if (self.include_dirs and (not any([self.fn.startswith(dir_) for dir_ in self.include_dirs]))) or \
           (self.exclude_dirs and any([self.fn.startswith(dir_) for dir_ in self.exclude_dirs])):
            self.exec_cmd_resp(b'return\n')
            time.sleep(0.01)
            # 这种情况要返回上一层, 不执行append_log
            
        if self.fn == log_info['filename'] and \
           (self.lno > log_info['lineno'] or self.fn == log_info['filename'] and self.is_return()):
            pass
        
        self.step_recursive(log_info, end_condition)
        
    def is_return(self):
        return

    def run(self, end_condition=None):
        if not end_condition:
            end_condition = lambda debug_handler: \
                debug_handler.entry_fn not in \
                debug_handler.exec_cmd_resp(b'bt\n', split_to_lines=False)
        if not self.entry_fn:
            fn, lno = self.get_curr_filename_lineno()
            self.entry_fn = fn
            self.fn, self.lno = fn, lno

        self.step_recursive(log_info=None, end_condition=end_condition)

if __name__ == '__main__':
    debug_client = DebugClient(host='127.0.0.1', port=8888)
    debug_client.run()
