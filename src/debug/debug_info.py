import os
import redis
import json


class DebugInfoRedis(object):
    
    def __init__(self, uri):
        self.client = redis.Redis.from_url(uri)
        self.key = 'DEBUG_INFO'
        
    def get_debug_info(self):
        resp_bytes = self.client.get('DEBUG_INFO')
        resp = json.loads(resp_bytes.decode('utf-8'))
        return resp

    def save_debug_info(self, debug_info):
        self.client.set('DEBUG_INFO', json.dumps(debug_info))

    def append_debug_logs(self, logs):
        pass


debug_info_helper = None
def get_debug_info_helper(uri=None):
    global debug_info_helper
    if not uri:
        uri = os.environ.get('DEBUG_INFO_URI')
    if not debug_info_helper:
        debug_info_helper = DebugInfoRedis(uri)

    return debug_info_helper
    


