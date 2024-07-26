import os
import epdb
import time
import uuid
import multiprocessing
from flask import Flask
from datetime import datetime

from .debug_saver import get_debug_saver_helper
from .debugger import DebugHelper

class DebugEntry(object):
    
    @classmethod
    def init_app(cls, app):
        debug_app = create_debug_app(app)
        debug_app.register_break_entry()
 

class AppDebugBase(object):
    
    def __init__(self, app):
        self.app = app
        self.saver_helper = get_debug_saver_helper()
        self.debug_helper = DebugHelper(include_dirs=[os.getcwd()], saver_helper=self.saver_helper)
        
    def get_app_routes(self):
        raise NotImplementedError()
        
    def get_matched_break(self, request, break_list):
        raise NotImplementedError()
        
    def register_break_entry(self):
        raise NotImplementedError()
    
    def get_app_routes(self):
        raise NotImplementedError()

class FlaskDebug(AppDebugBase):
    
    def get_app_routes(self, update=False):
        self.routes = {}
        for route_record in self.app.url_map.iter_rules():
            route = route_record.rule[:-1] if route_record.rule.endswith('/') else route_record.rule
            self.routes[route] = {'route': route, 'endpoint': route_record.endpoint, 'methods': route_record.methods}
            
        return self.routes
    
    def get_matched_break(self, request, break_list):
        request_route = request.path[:-1] if request.path.endswith('/') else request.path
        match_break_info = None
        for break_info in break_list:
            if break_info.get('type') != 'flask' or \
               (break_info.get('sn_list') and len(break_info['sn_list']) > break_info['sn_limit']):
                continue
            route = break_info['route']
            route = route[:-1] if route.endswith('/') else route
            if request_route == route:
                match_func_list = break_info.get('match_func') or []
                if not match_break_info or all(list(map(lambda x: eval(x)(request), match_func_list))):
                    match_break_info = break_info
                    break
        return match_break_info
    
    def get_tobreak_info(self, request):
        request_route = request.path[:-1] if request.path.endswith('/') else request.path
        endpoint = None
        for rule in self.app.url_map.iter_rules():
            rule_route = rule.rule[:-1] if rule.rule.endswith('/') else rule.rule
            if rule_route == request_route:
                endpoint = rule.endpoint
                break
        return {'endpoint': endpoint}
    
    def register_break_entry(self):
        def before_request_proc():
            from flask import current_app, request
            try:
                if self.saver_helper:
                    debug_info = self.saver_helper.get_debug_info()
                    break_list = debug_info.get('breaks') or []
                    break_info = self.get_matched_break(request, break_list)
                    if break_info and (not break_info.get('sn_list') or len(break_info['sn_list']) <= break_info['sn_limit']):
                        sn = f'{datetime.now().strftime("%Y%m%d%H%M%S")}_{str(uuid.uuid1()).replace('-', '')[:4]}' 
                        break_info['sn_list'].append(sn)
                        self.saver_helper.save_debug_info(debug_info)
                        
                        until_info = self.get_tobreak_info(request)

                        listen_port = self.debug_helper.get_listen_port()
                        process = multiprocessing.Process(target=self.conn_to_debugger_proc, args=(self.debug_helper, sn, listen_port, None, until_info))
                        process.daemon = True
                        #process.start()
                        self.debug_helper.listen_in_port(listen_port)
            except Exception as e:
                current_app.logger.error(f'flask api dynamic error: {e}')

        self.app.before_request(before_request_proc)
        
    @staticmethod
    def conn_to_debugger_proc(debug_helper, sn, conn_port, end_condition, until_info=None):
        for i in range(3):
            try:
                debug_helper.conn_to_port(conn_port)
                break
            except Exception as e:
                if i == 2: # last time
                    return
                time.sleep(1)
        if until_info:
            debug_helper.exec_cmd_resp(b'from flask import current_app\n')
            break_endpoint = until_info['endpoint']
            debug_helper.exec_cmd_resp(f'b current_app.view_functions["{break_endpoint}"]')
            debug_helper.exec_cmd_resp(b'continue')
        try:
            debug_helper.step_by_step(sn=sn, end_condition=end_condition)
        except Exception as e:
            print(e)

class FastApiDebug(AppDebugBase):
    pass

class CeleryDebug(AppDebugBase):
    pass

def create_debug_app(app):
    debug_app = None
    if isinstance(app, Flask):
        debug_app = FlaskDebug(app)
    return debug_app

if __name__ == '__main__':
    from src.debug.debug_saver import get_debug_saver_helper
    FlaskDebug.conn_to_debugger_proc(
        DebugHelper(include_dirs=[os.getcwd()], saver_helper=get_debug_saver_helper()),
        'aabbccdd',
        55188, #port
        None, #end_condition
        until_info={'endpoint': 'process_endpoint'}
    )
    
