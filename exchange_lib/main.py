
import random
import string
import threading
from concurrent.futures import ThreadPoolExecutor
from time import sleep

import bitmex

from exchange_lib.bitmex_ws import BitMEXWebsocket
from exchange_lib.events import Event
from tradingview.models import *
from tradingview.models import Order

logging.basicConfig(level=logging.INFO)
executor = ThreadPoolExecutor(max_workers=1)


class Exchange(Event):
    """
    Bitmex Exchange Object
    """
    def __init__(self, strategy, scrape_only=False):
        super().__init__()
        self.logger = logging.getLogger(__name__)

        self.logger.info("Initializing Exchange engine.")
        self.thread = threading.Thread(target=self.__start_exchange__)

        #  self.api = api
        self.strategy = strategy
        self.scrape_only = scrape_only
        self.api_key = self.strategy.api_key
        self.api_secret = self.strategy.api_secret
        if self.api_key == 'null' or self.api_secret == 'null':
            self.scrape_only = True
        self.logger.debug(f'API Keys: {self.api_key} : {self.api_secret}')
        self.thread.start()
        self.ws_restarting = False

        self.sellers = []

        self.buyers = []
        self.tv = 0
        self.last_buy = 0
        self.last_sell = 0
        self.trigers = []
        self.ws = None

    def gen_random_id(self, n: int = 12) -> object:
        """
        Generate a random password of length n
        :param n: length of password to generate
        :return: password string
        """
        random_source = string.ascii_letters + string.digits
        id_ = random.choice(string.ascii_lowercase)
        id_ += random.choice(string.ascii_uppercase)
        id_ += random.choice(string.digits)

        for i in range(n):
            id_ += random.choice(random_source)

        _list = list(id_)
        random.SystemRandom().shuffle(_list)
        clid = ''.join(_list)
        return clid

    def chase_order(self, order_id, side, avg, qty=None):
        """
        Limit Order Chasing - Ensure that our limit order is the first on the orderbook
        @param order_id: id of order to chase
        @param side: side of orderbook
        @param avg: price
        @param qty: quantity of order
        @return: --
        """
        sleep(1)  # takes a second for order_id to register in bitmex trade engine
        last_price = avg
        max_chase_buy = float(avg) + float(self.strategy.chase)
        max_chase_sell = float(avg) - float(self.strategy.chase)
        self.logger.info(f'Chasing {side} order, initial price: {avg}, chase: {self.strategy.chase}, '
                         f'Failsafe: {self.strategy.chase_failsafe} ')

        while True:
            # o = self.rest_open_order(orderID=order_id)
            o = self.ws_open_order(oid=order_id)
            if o:
                if side == 'Buy':
                    if self.strategy.double_check or self.ws_restarting:
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        _price = quote['bidPrice']
                    else:
                        _price = self.ws.get_ticker()['buy']

                    self.logger.debug(
                        f'Chasing buy order {order_id}, order_price: {avg}, last_price: {last_price}, current price: '
                        f'{_price} max chase: {max_chase_buy}')
                    if float(_price) <= float(max_chase_buy):
                        if float(last_price) < float(_price):
                            self.logger.info(f'Amending order {order_id} to price {_price}')
                            try:
                                ret = self.client.Order.Order_amend(orderID=order_id, price=_price).result()
                            except Exception as fuck:
                                self.logger.info(f'Error: {fuck}')
                            else:
                                self.logger.debug(ret)
                            finally:
                                last_price = _price
                        else:
                            self.logger.debug(f'Sleeping, order_price: {last_price}, current price: {_price}')
                            if self.strategy.double_check:
                                sleep(0.5)

                    else:
                        if self.strategy.chase_failsafe:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, buying market.')
                            self.client.Order.Order_cancelAll(symbol=self.strategy.symbol).result()
                            self.execute_order(oq=qty, ot='market', text='Chase failsafe market long order')
                        else:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, giving up.')
                        break
                elif side == 'Sell':
                    if self.strategy.double_check or self.ws_restarting:
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        _price = quote['askPrice']
                    else:
                        _price = self.ws.get_ticker()['sell']

                    self.logger.debug(
                        f'Chasing sell order {order_id}, order_price: {avg}, last_price: {last_price}, current price: '
                        f'{_price} max chase: {max_chase_sell}')
                    if float(_price) >= float(max_chase_sell):
                        if float(last_price) > float(_price):
                            self.logger.info(f'Amending order {order_id} to price {_price} ')
                            try:
                                ret = self.client.Order.Order_amend(orderID=order_id, price=_price).result()
                            except Exception as fuck:
                                self.logger.info(f'Error: {fuck}')
                            else:
                                self.logger.debug(ret)
                            finally:
                                last_price = _price
                        else:
                            self.logger.debug(f'Sleeping, order_price: {last_price}, current price: {_price}')
                            if self.strategy.double_check:
                                sleep(0.5)

                    else:
                        if self.strategy.chase_failsafe:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_sell}, selling market.')
                            self.client.Order.Order_cancelAll(symbol=self.strategy.symbol).result()
                            self.execute_order(oq=qty, ot='market', text='Chase failsafe market short order')
                        else:
                            self.logger.info(f'Price {_price} below max chase {max_chase_sell}, giving up.')
                        break
            else:
                self.logger.info('Order Filled')
                break

    def trailing_stop(self):
        """
        Trailing stop functionality via local bot logic
        @return:
        """
        # price = self.binance.get_price(self.market)
        pos = self.get_position()
        entry_price = pos['avgEntryPrice']
        qty = pos['currentQty']
        print('Trailing stop triggered')
        order_type = 'market'
        if qty > 0:
            # long position
            price = self.ws.get_ticker()['sell']
            offset_price = float(price) - float(self.strategy.trail_offset)
            text = 'Trailing sell stop for long position'
            qty = qty * -1
            side = 'Sell'
            print(f'Trailing Stop for long position triggered: offset price {offset_price}')
        elif qty < 0:
            # short position
            price = self.ws.get_ticker()['buy']
            offset_price = float(price) + float(self.strategy.trail_offset)
            text = 'Trailing buy stop for short position'
            qty = qty * -1
            side = 'Buy'
            print(f'Trailing Stop for short position triggered: offset price {offset_price}')
        else:
            self.logger.info('No position found!')
            return False

        while True:
            if side == "Sell":
                if self.strategy.double_check or self.ws_restarting:
                    quote = self.get_quote()
                    self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                    price = quote['askPrice']
                else:
                    price = self.ws.get_ticker()['sell']
                    self.logger.info('Bid: {} Ask: {}'.format(self.ws.get_ticker['buy'], self.ws.get_ticker['sell']))
                if (float(price) - float(self.strategy.trail_offset)) > float(offset_price):
                    offset_price = float(price) - float(self.strategy.trail_offset)
                    print("New high observed: Updating stop loss to %.8f" % offset_price)
                elif float(price) <= float(offset_price):
                    price = self.ws.get_ticker()['sell']
                    ret = self.execute_order(oq=qty, ot=order_type, text=text)
                    self.logger.info("Sell triggered | Price: %.8f | Stop loss: %.8f" % (price, offset_price))
                    self.logger.debug(ret)
                if self.strategy.double_check or self.ws_restarting:
                    sleep(0.5)
                    break

            if side == "Buy":
                if self.strategy.double_check or self.ws_restarting:
                    quote = self.get_quote()
                    self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                    price = quote['bidPrice']
                else:
                    price = self.ws.get_ticker()['buy']
                if (float(price) + float(self.strategy.trail_offset)) < float(offset_price):
                    offset_price = float(price) + float(self.strategy.trail_offset)
                    print("New low observed: Updating stop loss to %.8f" % offset_price)
                elif price >= offset_price:
                    price = self.ws.get_ticker()['buy']
                    ret = self.execute_order(oq=qty, ot=order_type, text=text)
                    self.logger.info("Buy triggered | Price: %.8f | Stop loss: %.8f" % (price, offset_price))
                    self.logger.debug(ret)
                    if self.strategy.double_check or self.ws_restarting:
                        sleep(0.5)
                    break

    def execute_order(self, oq, ot, text=None, trail_price=None):
        response = None
        while True:
            try:
                if ot == 'market':
                    response = self.client.Order.Order_new(
                        symbol=self.strategy.symbol,
                        orderQty=oq,
                        ordType='Market',
                        text=text,
                    ).result()
                    avg = response[0]['price']
                    quant = response[0]['orderQty']

                    self.logger.info(
                        "Market Order Placed: " + str(quant) + " contracts at " + str(avg) + " USD desc " + text)
                    break
                if ot == 'limit':
                    if self.strategy.double_check or self.ws_restarting:
                        """
                        Use rest api to double check price or rely on websocket
                        """
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        if float(oq) > float(0):
                            price = quote['bidPrice']
                        else:
                            price = quote['askPrice']
                    else:
                        quote = self.get_ticker()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['buy'], quote['sell']))
                        if float(oq) > float(0):
                            price = quote['buy']
                        else:
                            price = quote['sell']
                    response = self.client.Order.Order_new(
                        symbol=self.strategy.symbol,
                        orderQty=oq,
                        price=price,
                        text=text,
                        timeInForce='GoodTillCancel'
                    ).result()
                    avg = response[0]['price']
                    quant = response[0]['orderQty']
                    order_id = response[0]['orderID']
                    side = response[0]['side']

                    self.logger.info(
                        "Limit Order Placed: " + str(quant) + " contracts at " + str(avg) + " USD desc " + text)
                    if self.strategy.chase:
                        t = threading.Thread(target=self.chase_order, args=(order_id, side, avg, oq))
                        t.start()

                    break

                if ot == 'post':
                    if self.strategy.double_check or self.ws_restarting:
                        """
                        Use rest api to double check price or rely on websocket
                        """
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        if float(oq) > float(0):
                            price = quote['bidPrice']
                        else:
                            price = quote['askPrice']
                    else:
                        quote = self.get_ticker()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['buy'], quote['sell']))
                        if float(oq) > float(0):
                            price = quote['buy']
                        else:
                            price = quote['sell']
                    response = self.client.Order.Order_new(
                        symbol=self.strategy.symbol,
                        orderQty=oq,
                        price=price,
                        text=text,
                        execInst="ParticipateDoNotInitiate",
                        timeInForce='GoodTillCancel'
                    ).result()
                    if response[0]['ordStatus'] == 'Canceled' and "ParticipateDoNotInitiate" in response[0]['text']:
                        self.logger.error('ParticipateDoNotInitiate')
                        sleep(0.1)
                        continue
                    else:
                        avg = response[0]['price']
                        quant = response[0]['orderQty']
                        self.logger.info(
                            "Post Only Order Placed: " + str(quant) + " contracts at " + str(avg) + " USD desc " + text)
                        break
                if ot == 'trail_limit':
                    response = self.client.Order.Order_new(
                        symbol=self.strategy.symbol,
                        orderQty=oq,
                        price=trail_price,
                        text=text,
                        timeInForce='GoodTillCancel'
                    ).result()
                    avg = response[0]['price']
                    quant = response[0]['orderQty']
                    self.logger.info(
                        "Trailing Stop Order Placed: " + str(quant) + " contracts at " + str(avg) + " USD desc " + text)
                    break

            except Exception as ex:
                sleep(0.5)
                self.logger.error('Error executing order: ', ex)
                if any(item for item in ['400', '401', '403', '404'] if item in str(ex)):
                    raise ex

                continue
        return response[0]

    def get_quote(self):
        try:
            q = self.client.OrderBook.OrderBook_getL2(symbol=self.strategy.symbol, depth=1).result()
            # self.logger.info('quote {}'.format(q[0][0]))
            return {'askPrice': q[0][0]['price'], 'bidPrice': q[0][1]['price']}
        except Exception as ex:
            self.logger.error('error in quote')
            self.logger.error(ex)

    def rest_open_order(self, orderID):
        """
        Use the rest api to check if an order is open
        """
        o = self.client.Order.Order_getOrders(filter=json.dumps({"open": True, "orderID": orderID})).result()
        if o[0].__len__():
            return o[0][0]
        return None

    def ws_open_order(self, oid):
        """
        Use the WebSocket API to check if an order is open
        """
        open_orders = self.ws.open_orders('')
        if open_orders.__len__():
            for o in open_orders:
                if o['orderID'] == oid:
                    return o
        return None

    def update_strategy(self, strategy):
        self.strategy = strategy
        if strategy.api_key and self.api_key != strategy.api_key:
            self.api_key = strategy.api_key
            self.api_secret = strategy.api_secret
            self.client = bitmex.bitmex(test=False, api_key=self.api_key, api_secret=self.api_secret)

    def update_position(self):
        # self.logger.info('getting positions')
        if self.client:
            while True:
                try:
                    response = self.client.Position.Position_get(
                        filter=json.dumps({'symbol': self.strategy.symbol})).result()
                    if response and len(response[0]):
                        self.logger.debug('Positions {}'.format(response[0][0]))
                        self.p = (response[0][0]['openingQty'] + response[0][0]['execQty'])
                        break
                    else:
                        self.logger.info('no position found')
                        self.p = 0
                        break
                except Exception as ex:
                    sleep(0.1)
                    self.logger.error(str(ex))
                    continue
        else:
            self.p = 0

    def get_position(self):
        # self.logger.info('getting positions')
        if self.client:
            while True:
                try:
                    response = self.client.Position.Position_get(
                        filter=json.dumps({'symbol': self.strategy.symbol})).result()
                    if response and len(response[0]):
                        self.logger.debug('Positions {}'.format(response[0][0]))
                        pos = (response[0][0])
                        return pos
                    else:
                        self.logger.info('no position found')
                        break
                except Exception as ex:
                    sleep(0.1)
                    self.logger.error(str(ex))
                    continue
        else:
            self.p = 0

    def new_order(self, signal, type):
        """NEW ORDER FROM SCRAPER"""
        # self.client = bitmex.bitmex(test=True, api_key=self.strategy.api_key.key, api_secret=self.strategy.api_key.secret)
        if not self.strategy.live_trade:
            self.logger.info('Notice: Trading on testnet.')
        if self.scrape_only:
            return
        self.update_position()
        self.logger.info('New Order {} {}'.format(signal, type))
        self.logger.info("Current Position: {}".format(self.p))
        self.logger.info("Canceling all orders")
        self.client.Order.Order_cancelAll(symbol=self.strategy.symbol).result()
        self.trigers = []

        if type == 'entry' and signal == 'LONG' and self.p == 0:

            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            oq = self.strategy.contract_size
            ot = self.strategy.order_type
            try:
                self.logger.info("Placing LONG entry Order of {}".format(oq))
                order = self.execute_order(oq, ot, text="{} {}_{}".format(self.strategy.id, signal, type))
                if self.strategy.stop_loss:
                    triger = {
                        "side": -1,
                        "price": order['price'] - self.strategy.stop_loss,
                        "type": 'sl'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Stop loss trigger placed at {}'.format(triger['price']))
                if self.strategy.take_profit:
                    triger = {
                        'side': -1,
                        "price": order['price'] + self.strategy.take_profit,
                        "type": 'tp'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Take Profit trigger placed at {}'.format(triger['price']))
                if self.strategy.trailing_stop:
                    triger = {
                        'side': -1,
                        "price": order['price'] + self.strategy.trailing_stop,
                        'type': 'ts'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Trailing Stop trigger placed at {}'.format(triger['price']))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

        if type == 'entry' and signal == 'SHORT' and self.p == 0:
            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            oq = self.strategy.contract_size * -1
            ot = self.strategy.order_type
            try:
                self.logger.info("Placing Short entry Order of {}".format(oq))
                order = self.execute_order(oq, ot, text="{} {}_{}".format(self.strategy.id, signal, type))
                if self.strategy.stop_loss:
                    triger = {
                        "side": 1,
                        "price": order['price'] + self.strategy.stop_loss,
                        "type": 'sl'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Stop loss trigger placed at {}'.format(triger['price']))
                if self.strategy.take_profit:
                    triger = {
                        'side': 1,
                        "price": order['price'] - self.strategy.take_profit,
                        "type": 'tp'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Take profit trigger placed at {}'.format(triger['price']))
                if self.strategy.trailing_stop:
                    triger = {
                        'side': 1,
                        "price": order['price'] - self.strategy.trailing_stop,
                        'type': 'ts'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Trailing Stop trigger placed at {}'.format(triger['price']))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

        if type == 'entry' and signal == 'LONG' and self.p < 0:

            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            p = self.p * -1
            oq = p + self.strategy.contract_size
            ot = self.strategy.order_type
            try:
                self.logger.info("Placing LONG entry and Short Exit Order of {}".format(oq))
                order = self.execute_order(oq, ot, text="{} {}_{}-{}_{}".format(self.strategy.id, signal, type, "SHORT",
                                                                                "exit"))
                if self.strategy.stop_loss:
                    triger = {
                        "side": -1,
                        "price": order['price'] - self.strategy.stop_loss,
                        "type": 'sl'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Stop loss triger placed at {}'.format(triger['price']))
                if self.strategy.take_profit:
                    triger = {
                        'side': -1,
                        "price": order['price'] + self.strategy.take_profit,
                        "type": 'tp'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Take Profit triger placed at {}'.format(triger['price']))
                if self.strategy.trailing_stop:
                    triger = {
                        'side': -1,
                        "price": order['price'] + self.strategy.trailing_stop,
                        'type': 'ts'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Trailing Stop trigger placed at {}'.format(triger['price']))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

        if type == 'entry' and signal == 'SHORT' and self.p > 0:
            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            oq = -(self.p + self.strategy.contract_size)
            ot = self.strategy.order_type

            try:
                self.logger.info("Placing Short entry and Long Exit Order of {}".format(oq))
                order = self.execute_order(oq, ot,
                                           text="{} {}_{}-{}_{}".format(self.strategy.id, signal, type, "LONG", "exit"))
                if self.strategy.stop_loss:
                    triger = {
                        "side": 1,
                        "price": order['price'] + self.strategy.stop_loss,
                        "type": 'sl'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Stop loss triger placed at {}'.format(triger['price']))
                if self.strategy.take_profit:
                    triger = {
                        'side': 1,
                        "price": order['price'] - self.strategy.take_profit,
                        "type": 'tp'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Take Profit triger placed at {}'.format(triger['price']))
                if self.strategy.trailing_stop:
                    triger = {
                        'side': 1,
                        "price": order['price'] - self.strategy.trailing_stop,
                        'type': 'ts'
                    }
                    self.trigers.append(triger)
                    self.logger.info('Trailing Stop trigger placed at {}'.format(triger['price']))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

        if type == 'exit' and signal == 'LONG' and self.p > 0:
            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            oq = -(self.p)
            try:
                self.logger.info("Placing Long Exit Order of {}".format(oq))
                self.execute_order(oq, self.strategy.order_type, text="{} {}_{}".format(self.strategy.id, signal, type))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

        if type == 'exit' and signal == 'SHORT' and self.p < 0:
            # self.client.Order.Order_cancelAll(symbol = self.strategy.symbol).result()
            oq = -(self.p)
            try:
                self.logger.info("Placing Shot Exit Order of {}".format(oq))
                self.execute_order(oq, self.strategy.order_type, text="{} {}_{}".format(self.strategy.id, signal, type))
            except Exception as ex:
                self.logger.error("{}: Couldn't place order {}, {} ".format(self.strategy.id, signal, type))
                self.logger.error(str(ex))
                self.logger.error(repr(ex))

    def exit(self):
        self.ws.exit()

    def monitor_ws(self):
        """
        monitor the websocket for lag and restart if lag is detected, if signals come in while websocket
        is restarting, then bot will resort to rest api via self.ws_restarting parameter
        @return: --
        """
        started = False
        restart_count = 0
        while True:
            if not started or self.ws is None:
                self.ws = BitMEXWebsocket(endpoint="https://www.bitmex.com/api/v1", symbol=self.strategy.symbol,
                                          api_key=self.api_key, api_secret=self.api_secret)
                sleep(1)
                #try:
                if self.ws.started:
                    self.logger.info('Websocket is running.')
                    started = True
                    self.ws_restarting = False
                #except Exception as fuck:
                    #self.logger.error(f'Error in monitor_ws: {fuck}')
            else:
                if self.ws.lagging:
                    self.logger.error('Ws is lagging ,forcing a restart...')
                    self.ws.exit()
                    started = False
                    self.ws_restarting = True
                    restart_count += 1
                    self.logger.info(f'Ws starts this session: {restart_count}')

                else:
                    sleep(1)

    # @db_session(optimistic=False)
    def __start_exchange__(self):

        if self.scrape_only:
            self.ws = BitMEXWebsocket(endpoint="https://www.bitmex.com/api/v1", symbol=self.strategy.symbol,
                                      api_key=None, api_secret=None)
            self.logger.info('Scrape Only Mode: Not authenticating')
            self.ws_restarting = False
        else:
            if self.strategy.live_trade:

                # self.ws = BitMEXWebsocket(endpoint="https://www.bitmex.com/api/v1", symbol=self.strategy.symbol,
                #                          api_key=self.api_key, api_secret=self.api_secret)
                thread = threading.Thread(target=self.monitor_ws)
                thread.start()
                sleep(10)

                self.client = bitmex.bitmex(test=False, api_key=self.api_key, api_secret=self.api_secret)
                self.ws.on('quote_update', self.quote_update)
                self.logger.info('Exchange started')
                self.ws_restarting = False

            else:
                # self.ws = BitMEXWebsocket(endpoint="https://testnet.bitmex.com/api/v1", symbol=self.strategy.symbol,
                #                          api_key=None, api_secret=None)
                thread = threading.Thread(target=self.monitor_ws)
                thread.start()
                sleep(10)
                self.client = bitmex.bitmex(test=True, api_key=self.api_key, api_secret=self.api_secret)
                self.ws.on('quote_update', self.quote_update)
                self.logger.info('Testnet Exchange started')
                self.ws_restarting = False

    def get_ticker(self):
        return self.ws.get_ticker()

    # @db_session
    def entry_signal(self, signal):
        # {'chart': 'RHnQdy9T', 'symbol': self.strategy.symbol, 'status': 'unfilled',
        # 'tv': 819, 'type': 'entry', 'PnL': '', 'side': 'sell',
        # 'signal': 'SHORT', 'price': 8229.5, 'time': '2019-10-20 22:12',
        # 'strategy': 'RHnQdy9T'}
        #########################################
        # Order(strategy=signal['strategy'], tv=signal['tv'], signal=signal['signal'],
        # type=signal['type'], side=signal['side'], price=signal['price'],
        # status=signal['status'], position=0, time=datetime.now())
        self.logger.info('Entry Signal Called')
        try:
            ticker = self.get_ticker()
            self.logger.info('got ticker')

            signal['time'] = datetime.strptime(ticker['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
            # self.logger.info('signal time updated')
            if signal['signal'] == "LONG":
                for seller in self.sellers:
                    if seller['type'] == 'entry' and signal['strategy'] == seller['strategy']:
                        self.sellers.remove(seller)
                signal['price'] = ticker['buy']
                signal['position'] = 0
                self.logger.info('saving signal')
                self.save_signal(signal)
                order = signal.copy()
                order['position'] = 1
                order['status'] = 'filled'
                self.logger.info('saving order')
                self.buyers.append(order)
            if signal['signal'] == "SHORT":
                for buyer in self.buyers:
                    if buyer['type'] == 'entry' and signal['strategy'] == buyer['strategy']:
                        # self.logger.debug('buyer entry removed {}'.format(seller))
                        self.buyers.remove(buyer)
                signal['price'] = ticker['sell']
                signal['position'] = 0
                # self.logger.info('saving signal')
                self.save_signal(signal)
                order = signal.copy()
                order['position'] = -1
                order['status'] = 'filled'
                # self.logger.info('saving order')
                self.sellers.append(order)
        except Exception as ex:
            self.logger.error('Error on entry Order')
            self.logger.error(str(ex))
            self.logger.error(repr(ex))

    # @db_session
    def exit_signal(self, signal):
        self.logger.info('Exit Signal Called')
        try:
            ticker = self.get_ticker()
            # self.logger.info('got ticker')
            signal['time'] = datetime.strptime(ticker['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
            # self.logger.info('time updated')
            if signal['signal'] == 'LONG':
                for buyer in self.buyers:
                    if buyer['type'] == 'entry' and signal['strategy'] == buyer['strategy']:
                        self.buyers.remove(buyer)
                        self.logger.info('buyer removed {}'.format(buyer))
                signal['price'] = ticker['sell']
                self.logger.info('getting entry filled signal for {}'.format(signal))
                entry = Order.select(lambda s: s.strategy.id == signal['strategy'] and s.tv == signal[
                    'tv'] and s.type == 'entry' and s.status == 'filled').first()
                # entry = select(strategy=signal['strategy'], tv=signal['tv'])
                # self.logger.info('entry {}'.format(entry))
                # print(f'Entry: {entry}')
                if entry:
                    # self.logger.info('entry buy price {}'.format(entry.price))
                    signal['position'] = 1
                    self.save_signal(signal)
                    order = signal.copy()
                    order['position'] = 0
                    order['status'] = 'filled'
                    order['PnL'] = self.PNL(entry.price, signal['price'])
                    # self.logger.info('Placing LONG Exit Order at sell Price: {}'.format(signal['price']))
                    self.sellers.append(order)
                else:
                    signal['position'] = 0
                    self.save_signal(signal)
            if signal['signal'] == 'SHORT':
                for seller in self.sellers:
                    if seller['type'] == 'entry' and signal['strategy'] == seller['strategy']:
                        self.sellers.remove(seller)
                # self.logger.info('getting entry filled signal for {}'.format(signal))
                entry = Order.select(lambda s: s.strategy.id == signal['strategy'] and s.tv == signal[
                    'tv'] and s.type == 'entry' and s.status == 'filled').first()
                # entry = select(strategy=signal['strategy'], tv=signal['tv'])
                # self.logger.info('entry {}'.format(entry))
                print(f'Entry: {entry}')

                signal['price'] = ticker['buy']
                if entry:
                    # self.logger.info('entry sell price {}'.format(entry.price))
                    signal['position'] = -1
                    self.save_signal(signal)
                    order = signal.copy()
                    order['position'] = 0
                    order['status'] = 'filled'
                    order['PnL'] = self.PNL(signal['price'], entry.price)
                    # self.logger.info('Placing SHORT Exit Order at buy Price: {}'.format(signal['price']))
                    self.buyers.append(order)
                else:
                    signal['position'] = 0
                    self.save_signal(signal)
        except Exception as ex:
            self.logger.error('error while processing exit signal')
            self.logger.error(str(ex))
            self.logger.error(repr(ex))

    # @db_session
    def save_signal(self, signal):
        self.logger.info(
            'Saving signal => Strategy: {} Order: {} Type: {} Side: {} Price: {} Status: {}'.format(signal['strategy'],
                                                                                                    signal['signal'],
                                                                                                    signal['type'],
                                                                                                    signal['side'],
                                                                                                    signal['price'],
                                                                                                    signal['status']))
        if signal['type'] == 'exit' and signal['status'] == 'filled':
            Order(strategy=signal['strategy'], tv=signal['tv'], signal=signal['signal'],
                  trade=signal['trade'],
                  type=signal['type'], side=signal['side'], price=signal['price'],
                  status=signal['status'], position=signal['position'], time=signal['time'], PnL=signal['PnL'])
        else:

            Order(strategy=signal['strategy'], tv=signal['tv'], signal=signal['signal'],
                  type=signal['type'], side=signal['side'], price=signal['price'],
                  trade=signal['trade'],
                  status=signal['status'], position=signal['position'], time=signal['time'])

    def quote_update(self, ticker):

        buy = ticker['buy']
        sell = ticker['sell']
        # %d/%m/%y %H:%M:%S.%f
        # timestamp = datetime.strptime(ticker['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
        # timestamp = datetime.st(orderbook[0]['timestamp'].replace('Z', ''))

        if self.last_buy != buy or self.last_sell != sell:
            self.last_buy = buy
            self.last_sell = sell
            for triger in self.trigers:
                if triger['type'] == 'sl':
                    if triger['side'] == -1:
                        if sell <= triger['price']:
                            self.logger.info('Stop loss triger for long entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p > 0:
                                oq = -(self.p)
                                ot = self.strategy.sl_type
                                self.execute_order(oq, ot, '{} LONG_sl'.format(self.strategy.id))
                                self.trigers.remove(triger)
                    if triger['side'] == 1:
                        if buy >= triger['price']:
                            self.logger.info('Stop loss triger for Short entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p < 0:
                                oq = -(self.p)
                                ot = self.strategy.sl_type
                                self.execute_order(oq, ot, '{} SHORT_sl'.format(self.strategy.id))
                                self.trigers.remove(triger)
                if triger['type'] == 'tp':
                    if triger['side'] == -1:
                        if sell >= triger['price']:
                            self.logger.info('Take profit trigger for Long entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p > 0:
                                oq = -self.p
                                ot = self.strategy.order_type
                                self.execute_order(oq, ot, '{} LONG_tp'.format(self.strategy.id))
                                self.trigers.remove(triger)
                    if triger['side'] == 1:
                        if buy <= triger['price']:
                            self.logger.info('Take profit trigger for Short entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p < 0:
                                oq = -self.p
                                ot = self.strategy.order_type
                                self.execute_order(oq, ot, '{} SHORT_tp'.format(self.strategy.id))
                                self.trigers.remove(triger)
                if triger['type'] == 'ts':
                    if triger['side'] == -1:
                        if sell >= triger['price']:
                            self.logger.info('Trailing Stop trigger for Long entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p > 0:
                                print('Debug: Trailing stop for long')
                                t = threading.Thread(target=self.trailing_stop)
                                t.start()
                                self.trigers.remove(triger)
                    if triger['side'] == 1:
                        if buy <= triger['price']:
                            self.logger.info('Trailing Stop trigger for Shoty entry at {}'.format(triger['price']))
                            self.update_position()
                            if self.p < 0:
                                print('Debug: Trailing stop for short')
                                t = threading.Thread(target=self.trailing_stop)
                                t.start()
                                self.trigers.remove(triger)

    """"#@db_session
    def update_stats(self, signal):
        start_date = min(s.time for s in Order if s.strategy.id == signal['strategy'])
        end_date = max(s.time for s in Order if s.strategy.id == signal['strategy'])
        duration = end_date - start_date
        roi = sum(s.PnL for s in Order if s.strategy.id == signal['strategy'])
        total_trades = count(s for s in Order if s.strategy.id == signal['strategy'] and s.PnL is not None)
        if duration.days == 0:
            roi_per_day = roi
        else:
            roi_per_day = roi / duration.days
        totsec = duration.total_seconds()
        h = totsec // 3600
        if h <= 0:
            trades_per_hour = total_trades
        else:
            trades_per_hour = int(total_trades / h)
        wins = count(s for s in Order if s.strategy.id == signal['strategy'] and s.PnL is not None and s.PnL > 0)
        losses = count(s for s in Order if s.strategy.id == signal['strategy'] and s.PnL is not None and s.PnL <= 0)
        ts = select(s.tv for s in Order if s.strategy.id == signal['strategy'])[:]
        ts_set = set(ts)
        ul = (list(ts_set))
        neutral = len(ul) - total_trades
        entry = Order.select(
            lambda s: s.strategy.id == signal['strategy'] and s.trade.id == signal['trade'] and s.type == signal[
                'type'] and s.status == signal['status'] and s.price == signal['price']).first()
        entry.duration = "{} day(s) - {} hour(s)".format(duration.days, int(h - (duration.days * 24)))
        entry.roi_per_day = roi_per_day
        entry.trades_per_hour = trades_per_hour
        entry.wins = wins
        entry.losses = losses
        entry.neutral = neutral"""

    def PNL(self, buy, sell):
        try:
            pnl = float("{0:.2f}".format(((float(sell) - float(buy)) / float(buy)) * 100))
            return pnl
        except Exception:
            return 0.0
