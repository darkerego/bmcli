class Event:
    def __init__(self):
        self.listeners = []
        self.callbacks = {}
    def on(self, event_name, callback):
        if event_name not in self.callbacks:
            self.callbacks[event_name] = [callback]
        else:
            self.callbacks[event_name].append(callback)

    def emit(self, event_name, data):
        if self.callbacks is not None and event_name in self.callbacks:
            for callback in self.callbacks[event_name]:
                callback(data)