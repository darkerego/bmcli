"""Configuration File"""
testnet = False
from bmexlib.config_tool import ReadWriteConfig
# Generate multiple API keys so you can work with different instruments with websockets at once, example:
"""
{'config': [{'keys': [[{'XBTUSD': {'key': 'xxxxxxxxxxxxxx', 'secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}}], 
[{'ETHUSD': {'key': 'xxxxxxxxxxxxxxxxxx', 'secret': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}}]]}]}

"""
# ^ Store that in bmexlib/config.json


rwc = ReadWriteConfig()
config = rwc.read_config('bmexlib/config.json') # <-- ADD YOUR API KEYS TO THIS FILE
keys = config['config'][0]['keys']

api_key = keys[0][0]['XBTUSD']['key']
api_secret = keys[0][0]['XBTUSD']['secret']
api_key_alt = keys[1][0]['ETHUSD']['key']
api_secret_alt = keys[1][0]['ETHUSD']['secret']

# MqTT Options
class MqTTConfig():
    SUBSCRIPTIONS = [('/bitmex/stdin', 0)]
    mq_bindAddress = '0.0.0.0'
    mq_host = '127.0.0.1'
    mq_port = 1883
    mq_keepalive = 60
    mq_user = 'bmex_bot'
    mq_pass = 'bitmex_1234!'
    mq_pubtop = '/bitmex/stdio'
    mq_subtop = '/bitmex/stdin'
    verbose = True

