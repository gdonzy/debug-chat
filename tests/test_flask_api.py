import os
from flask import Flask, jsonify, request
from src.debug.debug_apps import DebugEntry

app = Flask(__name__)
DebugEntry.init_app(app)

def process_data(data):
    # 模拟处理数据的函数
    processed_data = data.upper()  # 例如，将字符串转换为大写
    return processed_data

@app.route('/process', methods=['POST'])
def process_endpoint():
    input_data = request.json.get('data')
    if not input_data:
        return jsonify({"error": "No data provided"}), 400

    result = process_data(input_data)
    
    return jsonify({"processed_data": result})

def update_redis_info(debug_info_uri):
    import json
    import redis
    
    client = redis.StrictRedis.from_url(debug_info_uri)

    debug_info = {
        'breaks': [{
            'type': 'flask',
            'route': '/process',
            'match_func': ['lambda x: True'],
            'sn_limit': 30,
            'sn_list': [],
        }, {
            'type': 'celery',
            'route': '',
            'match_func': ['lambda x: True'],
            'sn_limit': 30,
            'sn_list': [],
        }],
    }
    try:
        client.set('DEBUG_INFO', json.dumps(debug_info))
    except Exception as e:
        print(f'set debug info in redis error: {e}')
    
    os.environ['DEBUG_INFO_URI'] = debug_info_uri

if __name__ == '__main__':
    update_redis_info('redis://127.0.0.1:6379/0')
    app.run(debug=False)
# curl -X POST -H "Content-Type: application/json" -d '{"data": "hello"}' http://127.0.0.1:5000/process
