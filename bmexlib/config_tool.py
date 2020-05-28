import json

class ReadWriteConfig:

    def pp_json(self, json_thing, sort=True, indents=4):
        if type(json_thing) is str:
            print(json.dumps(json.loads(json_thing), sort_keys=sort, indent=indents))
        else:
            print(json.dumps(json_thing, sort_keys=sort, indent=indents))
        return None

    def write_config(self, file='test.json', conf_json={}):
        with open(file, 'w') as jf:
            try:
                json.dump(conf_json, jf)
            except Exception as fuck:
                print(f'Error: {fuck}')
                return False
            return

    def read_config(self, file='config.json'):
        with open(file, 'r') as f:
            config = json.load(f)
            return config

    def test_my_config(self, jdata={}, fnmame='config.json'):
        print('Try to read your json data ...')
        try:
            self.pp_json(jdata)
        except Exception as err:
            print('Error with your json: ', err)
        else:
            print('Testing if we can read and write json to disc...')
            try:
                self.write_config(file='test.json', conf_json=jdata)
            except Exception as err:
                print('Error with your json: ', err)
            else:
                try:
                    self.read_config(fnmame)
                except Exception as err:
                    print('Error with your json: ', err)
                else:
                    print('Test succeeded!')