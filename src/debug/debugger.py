import re
import time
import re
import time
import socket
import telnetlib
from pprint import pprint
from remote_pdb import RemotePdb

from .code_proc import get_py_lno_vars_map

class DebugHelper(object):
    bt_lineinfo_pattern = re.compile(r'^>?\s*(.+)\((\d+)\)(.+)\(')
    
    def __init__(self, host='127.0.0.1', port=None, include_dirs=None, exclude_dirs=None, saver_helper=None):
        """
        port：如果传入，则使用传入的，如果没有传入，则使用随机端口
        """
        self.host = host
        self.port = port
        self.client = None
        self.entry_fn = None
        self.logs = {}
        self.include_dirs = include_dirs or []
        self.exclude_dirs = exclude_dirs or []
        self.retval_list = []
        self.fn_lno_vars = {}
        self.saver_helper = saver_helper
    
    def get_listen_port(self):
        if self.port:
            return port

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            port = s.getsockname()[1]
            return port
        
    def listen_in_port(self, port):
        #epdb.serve(port=port)
        RemotePdb(self.host, port).set_trace()
    
    def conn_to_port(self, port):
        #self.client = epdb.epdb_client.TelnetClient(self.host, port) # donot use telnetlib、epdb.connect
        self.client = telnetlib.Telnet(self.host, port)
        return self.client
    
    def exec_cmd(self, cmd):
        if isinstance(cmd, str):
            cmd = cmd.encode('ascii')
        if not cmd.endswith(b'\n'):
            cmd += b'\n'
        self.client.write(cmd)

    def get_resp(self):
        resp_bytes = b''
        for i in range(5):
            part_bytes = self.client.read_very_eager()
            if part_bytes:
                resp_bytes += part_bytes
            else:
                time.sleep(0.002)
        resp = resp_bytes.decode('utf-8')
        return resp
    
    def exec_cmd_resp(self, cmd, split_to_lines=True):
        self.exec_cmd(cmd)
        resp = self.get_resp()
        if split_to_lines:
            return resp.split('\n')
        else:
            return resp

    def get_lineinfo_by_lelvel(self, level=0):
        """
        level: 0表示当前frame，1表示上一层frame，2表示上2层frame，以此类推
        """
        lines = self.exec_cmd_resp(b'bt\n')
        lineinfo_list = []
        for l in lines[:-(2*level+5):-1]:
            if self.bt_lineinfo_pattern.match(l):
                match = self.bt_lineinfo_pattern.search(l)
                fn = match.group(1)
                try:
                    lno = int(match.group(2))
                except Exception as e:
                    print(e)
                func = match.group(3)
                lineinfo_list.append((fn, lno, func))
            if len(lineinfo_list) >= level+1:
                break
        return lineinfo_list[level] if len(lineinfo_list) > level else (None, None, None)
    
    def _get_local_vars_in_lno(self, fn, lno):
        lno_vars = {}
        var_name_list = self.fn_lno_vars[fn].get(lno) or []
        for var_name in var_name_list:
            if var_name in self.locals:
                lno_vars[var_name] = self.locals[var_name]
                
        return lno_vars
        
    def proc_logs(self):
        # 相关key如果self.logs中没有初始化则初始化
        log_key = f'{self.fn}::{self.func}'
        if log_key not in self.logs:
            self.logs[log_key] = {}
        if self.lno not in self.logs[log_key]:
            self.logs[log_key][self.lno] = {
                'before': {}, 'after': {},
                'last': {'fn': self.last_fn, 'lno': self.last_lno, 'func': self.last_func}
            }

        # 当前行的执行前before字段中变量值更新
        if not self.logs[log_key][self.lno]['before']:
            lno_vars = self._get_local_vars_in_lno(self.fn, self.lno)
            self.logs[log_key][self.lno]['before'].update(lno_vars)
        # 当前行之前行执行后after字段中变量值更新
        lno_list = sorted([lno_ for lno_, log_info in self.logs[log_key].items() if lno_ < self.lno and (not log_info)])
        if self.retval_list and lno_list:
            self.logs[log_key][lno_list[-1]]['after']['__retval__'] = self.retval_list
            self.retval_list = []
        for lno in lno_list:
            if not self.logs[log_key][lno]['after']:
                lno_vars = self._get_local_vars_in_lno(self.fn, lno)
                self.logs[log_key][lno]['after'].update(lno_vars)
    
    def get_locals(self):
        locals_resp = self.exec_cmd_resp(b'p f\'+++{"".join([k+":=:"+str(v)+"===" for k,v in locals().items()])}---\'\n', split_to_lines=False)
        start_idx, end_idx = (locals_resp.index('+++')+3), locals_resp.index('---')
        valid_resp = locals_resp[start_idx:end_idx]
        locals = {}
        for item in valid_resp.split('==='):
            item = item.strip()
            if item and ':=:' in item:
                var_, val_ = item.split(':=:')
                locals[var_] = val_
        return locals

    def step_by_step(self, sn=None, end_condition=None):
        self.last_fn, self.last_lno, self.last_func = None, None, None
        self.fn, self.lno, self.func = self.get_lineinfo_by_lelvel(level=0)
        self.entry_fn = self.fn
        self.entry_func = self.func
        if not end_condition:
            end_condition = lambda debug_handler: \
                debug_handler.entry_fn not in \
                debug_handler.exec_cmd_resp(b'bt\n', split_to_lines=False)
                
        while not end_condition(self):
            fn, lno, func = self.get_lineinfo_by_lelvel(level=0)
            # 当前代码运行位置文件 不在_include_dirs中 或 在exclude_dirs中，则直接到return
            if (self.include_dirs and (not any([fn.startswith(dir_) for dir_ in self.include_dirs]))) or \
               (self.exclude_dirs and any([fn.startswith(dir_) for dir_ in self.exclude_dirs])):
                self.exec_cmd_resp(b'return\n')
                self.exec_cmd_resp(b'n\n')
                fn, lno, func = self.get_lineinfo_by_lelvel(level=0)

            # return位置的话，要返回，并更新self.retval_list
            self.locals = self.get_locals()
            if '__return__' in self.locals: #使用locals,而不使用retval,主要是locals后续可能用到，不用重复查
                self.retval_list.append({
                    'fn': self.fn, 'func': self.func, 'lno': self.lno,
                    'retval': self.locals['__return__']
                })

            if (fn, func) != (self.fn, self.func) and (fn, func) == (self.last_fn, self.last_func):
            # 刚从函数中返回，回到上一层frame
                self.last_fn, self.last_lno, self.last_func = self.get_lineinfo_by_lelvel(level=1)
            elif (fn, func) != (self.fn, self.func) and (fn, func) != (self.last_fn, self.last_func):
            # 刚调用了一个函数，去到下一层frame
                self.last_fn, self.last_lno, self.last_func = self.fn, self.lno, self.func

            self.fn, self.lno, self.func = fn, lno, func
            if self.fn not in self.fn_lno_vars:
                self.fn_lno_vars[self.fn] = get_py_lno_vars_map(self.fn)
            self.proc_logs()
                
            self.exec_cmd_resp(b's\n')
            
        pprint(self.logs)
        self.saver_helper.update_debug_logs(sn, self.logs)
        self.exec_cmd(b'continue\n')
