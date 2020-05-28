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
config = rwc.read_config('bmexlib/config.json') #  copy config.example.json to config.json and add your api keys!
keys = config['config'][0]['keys']

api_key = keys[0][0]['XBTUSD']['key']
api_secret = keys[0][0]['XBTUSD']['secret']
api_key_alt = keys[1][0]['ETHUSD']['key']
api_secret_alt = keys[1][0]['ETHUSD']['secret']


