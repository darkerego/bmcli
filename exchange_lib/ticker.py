debug = True


class Ticker:
    def __init__(self, exchange=None, pair=None, mode=None):
        global NAME
        self.exchange = exchange
        self.pair = pair
        self.mode = mode
        self.ask = 0.0
        self.bid = 0.0
        self.last = 0.0
        self.mid = 0.0
        if self.exchange or self.pair is not None:
            self.name = self.pair+'_'+self.exchange
            NAME = self.name
            if debug:
                print('Init new ticker %s' % NAME)
            #Ticker.all_tickers.append()

    def update(self, bid=0.0, ask=0.0, last=0.0, mid=0.0):

        self.ask = ask
        self.bid = bid
        self.last = last
        self.mid = mid
        if debug:
            print('Updated '+str(self.pair)+' '+str(self.exchange)+'  ticker to bid: '+str(bid)+' ask : '+str(ask))

    def get(self, mode):
        ask = self.ask
        bid = self.bid
        last = self.last
        mid = self.mid
        self.mode = mode
        if float(ask) > 0.0 and float(bid) > 0.0:
            if mode == 'ask':
                return ask
            elif mode == 'bid':
                return bid
            elif mode == 'last':
                return last
            elif mode == 'mid':
                return mid
        else:
            return False
