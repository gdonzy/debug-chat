import os
import redis
import json
import copy


class DebugSaverRedis(object):
    
    def __init__(self, uri):
        self.client = redis.Redis.from_url(uri)
        
    def get_debug_info(self):
        resp_bytes = self.client.get('DEBUG_INFO')
        resp = json.loads(resp_bytes.decode('utf-8'))
        return resp

    def save_debug_info(self, debug_info):
        self.client.set('DEBUG_INFO', json.dumps(debug_info))
        return debug_info

    def update_debug_logs(self, sn, logs):
        self.client.set(f'DEBUG_LOG:{sn}', json.dumps(logs))
    
    def get_debug_logs_by_seq(self, sn):
        logs_bytes = self.get(f'DEBUG_LOG:{sn}')
        logs = json.loads(logs_bytes.decode('utf-8'))
        return logs
    
    def get_debug_log_source_list(self, break_type=None, break_route=None):
        debug_info = self.get_debug_info()
        break_list = debug_info.get('breaks') or []

        if break_list and (break_type or break_route):
            break_conditions = []
            if break_type:
                break_conditions.append(lambda break_info: break_info['type'] == break_type)
            if break_route:
                break_conditions.append(lambda break_info: break_info['route'] == break_route)
            break_list = [
                break_info
                for break_info in break_list
                if all(break_conditions)
            ]

        log_sn_list = self.client.keys('DEBUG_LOG:*')
        sn_list = [log_sn.replace('DEBUG_LOG:', '') for log_sn in log_sn_list]
        
        ret = []
        for break_info in break_list:
            shared_sn_list = set(break_info['sn_list']) & set(sn_list)
            break_copy = copy.deepcopy(break_info)
            break_copy['sn_list'] = list(shared_sn_list)
            ret.append(ret)

        return ret

debug_saver_helper = None
def get_debug_saver_helper(uri=None):
    global debug_saver_helper
    uri = uri or os.environ.get('DEBUG_INFO_URI')
    if uri and (not debug_saver_helper):
        debug_saver_helper = DebugSaverRedis(uri)

    return debug_saver_helper

if __name__ == '__main__':
    dh = get_debug_saver_helper(uri='')

