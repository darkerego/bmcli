import threading
import bitmex
import time
import json
from exchange_lib.bitmex_ws import BitMEXWebsocket
import logging
#import mqtt_lib.mqtt_skel as mq
from datetime import datetime as dt, timezone
from datetime import timedelta
from SyBrain.stocks import Main  # Machine Learning Module
import pandas as pd
from time import sleep
import datetime
from colorama import Fore, Back, Style, init
#from SyBrain.sybrain import
logging.basicConfig(level=logging.INFO, format=(Fore.BLUE + '[+] ' + Style.RESET_ALL + '%(message)s '))
init(autoreset=True)


#########################################

matrix_bmex_ticker = [None] * 3
matrix_bmex_trade = [None] * 5

matrix_bmex_fairPrice = [None] * 10
matrix_bmex_fairPrice_var = [None] * 10
tick_count = 0
tick_ok = False
pos_taken = 0

def timestamp():
    """
    Get current time
    @return: string timestamp
    """
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return str(st)

def pretty_text(text):
    return Fore.RED + '[ ' + Style.RESET_ALL + str(text) + Fore.BLUE + ' ]'

class BitmexApiTool:
    """
    Bitmex Functions Library
    """

    def __init__(self, symbol='XBTUSD', api_key=None, api_secret=None, test_net=False, require_ws=False, pos_size=None):
        self.triggered = False
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.test_net = test_net
        self.require_ws = require_ws
        self.logger = logging.getLogger(__name__)
        self.ws = None
        self.pos_size = pos_size

        if self.test_net:
            self.client = bitmex.bitmex(test=True, api_key=self.api_key, api_secret=self.api_secret)
            if self.require_ws:
                self.ws = BitMEXWebsocket(endpoint="https://testnet.bitmex.com/api/v1", symbol=self.symbol,
                                          api_key=self.api_key, api_secret=api_secret)

        else:

            self.client = bitmex.bitmex(test=False, api_key=self.api_key, api_secret=self.api_secret)
            if self.require_ws:
                self.ws = BitMEXWebsocket(endpoint="https://www.bitmex.com/api/v1", symbol=self.symbol,
                                          api_key=self.api_key,
                                          api_secret=self.api_secret)

    def monitor_ws(self, endpoint='https://www.bitmex.com/api/v1'):  #TODO: implement
        """
        monitor the websocket for lag and restart if lag is detected, if signals come in while websocket
        is restarting, then bot will resort to rest api via self.ws_restarting parameter
        @return: --
        """
        started = False
        restart_count = 0
        while True:
            if not started or self.ws.exited or self.ws is None:
                self.ws = BitMEXWebsocket(endpoint=endpoint, symbol=self.symbol,
                                          api_key=self.api_key, api_secret=self.api_secret)
                time.sleep(1)
                if self.ws.started:
                    self.logger.info('Websocket is running.')
                    started = True
                    self.ws_restarting = False
            else:
                if self.ws.lagging:
                    self.logger.error('Ws is lagging ,forcing a restart...')
                    self.ws.exit()
                    started = False
                    self.ws_restarting = True
                    restart_count += 1
                    self.logger.info(f'Ws starts this session: {restart_count}')

                else:
                    time.sleep(1)

    def rounded_price(self, number, symbol):
        if symbol == "XBTUSD":
            return round(number * 2.0) / 2.0
        elif symbol == "ETHUSD":
            return round(number * 20.0) / 20.0

    def get_balance(self):
        """
        ({'account': 1428629, 'currency': 'XBt', 'riskLimit': 1000000000000, 'prevState': '', 'state': '', 'action': '',
         'amount': 2461088, 'pendingCredit': 0, 'pendingDebit': 0, 'confirmedDebit': 0, 'prevRealisedPnl': 22872,
         'prevUnrealisedPnl': 0, 'grossComm': 1128, 'grossOpenCost': 0, 'grossOpenPremium': 0, 'grossExecCost': 0,
         'grossMarkValue': 21360000, 'riskValue': 21360000, 'taxableMargin': 0, 'initMargin': 0, 'maintMargin': 597644,
         'sessionMargin': 0, 'targetExcessMargin': 0, 'varMargin': 0, 'realisedPnl': -194128, 'unrealisedPnl': -30000,
         'indicativeTax': 0, 'unrealisedProfit': 0, 'syntheticMargin': 0, 'walletBalance': 2266960,
         'marginBalance': 2236960, 'marginBalancePcnt': 0.1047, 'marginLeverage': 9.548673199341964,
         'marginUsedPcnt': 0.2672, 'excessMargin': 1639316, 'excessMarginPcnt': 0.0767, 'availableMargin': 1639316,
         'withdrawableMargin': 1639316, 'timestamp': datetime.datetime(2020, 5, 20, 3, 8, 15, 462000, tzinfo=tzutc()),
         'grossLastValue': 21360000, 'commission': 0.0},
         <bravado.requests_client.RequestsResponseAdapter object at 0x7fcca9d34510>)
        """
        return self.client.User.User_getMargin().result()[0]['walletBalance']

    def get_raw(self):
        """
        Raw margain data
        @return:
        """
        return self.client.User.User_getMargin().result()[0]

    def get_position(self):
        # self.logger.info('getting positions')
        if self.client:
            while True:
                try:
                    response = self.client.Position.Position_get(filter=json.dumps({'symbol': self.symbol})).result()
                    if response and len(response[0]):
                        self.logger.debug('Positions {}'.format(response[0][0]))
                        # p = (response[0][0]['openingQty'] + response[0][0]['execQty'])
                        p = response[0][0]
                        return p
                    else:
                        self.logger.info('no position found')
                        p = 0
                        return p
                except Exception as ex:
                    time.sleep(0.1)
                    self.logger.error(str(ex))
                    continue
        else:
            p = 0

    def ws_orders(self, orderID):
        orders = self.ws.open_orders('')
        if orders.__len__():
            for o in orders:
                if o['orderID'] == orderID:
                    return o
        return None

    def rest_open_order(self, orderID=None):
        """
        Use the rest api to check if an order is open
        """
        if orderID:
            o = self.client.Order.Order_getOrders(filter=json.dumps({"open": True, "orderID": orderID})).result()
        else:
            o = self.client.Order.Order_getOrders(filter=json.dumps({"open": True}))
        if o:
            return o.result()[0]
        return None

    def get_quote(self):
        try:
            q = self.client.OrderBook.OrderBook_getL2(symbol=self.symbol, depth=1).result()
            self.logger.info('quote {}'.format(q[0][0]))
            return {'buy': q[0][0]['price'], 'sell': q[0][1]['price']}
        except Exception as ex:
            self.logger.error('error in quote')
            self.logger.error(ex)

    def get_pnl(self):
        pnl = self.get_raw()
        realized = pnl['realisedPnl']
        unrealized = pnl['unrealisedPnl']
        balance = pnl['walletBalance']
        return realized, unrealized, balance

    def send_order(self, oq, ot, text='bmx_api_tool', price=None,  stopPx=0.0, pegOffsetValue=0, double_check=False):
        if price is None:
            if self.ws and not double_check:
                quote = self.ws.get_ticker()
            else:
                quote = self.get_quote()

            if float(oq) > float(0):
                price = quote['buy']
                side = 'buy'
            else:
                side = 'sell'
                price = quote['sell']
            if price > 0:
                self.logger.info(f'Sending {side} order for {oq} at {price} , order type: {ot}')
        if ot == 'post':
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                price=price,
                text=text,
                timeInForce='GoodTillCancel',
                execInst="ParticipateDoNotInitiate",
            ).result()
        elif ot == 'market':
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                ordType='Market',
                text=text,
            ).result()
        elif ot == 'Stop':
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                ordType='Stop',
                text=text,
                stopPx=stopPx
            ).result()
        elif ot == 'StopLimit':
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                ordType='Stop',
                text=text,
                price=price,
                stopPx=stopPx
            ).result()
        elif ot == 'LimitIfTouched':
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                ordType='LimitIfTouched',
                text=text,
                price=price,
                stopPx=stopPx,
                pegOffsetValue=pegOffsetValue,
                pegPriceType='TrailingStopPeg'
            ).result()
        else:  # Limit
            response = self.client.Order.Order_new(
                symbol=self.symbol,
                orderQty=oq,
                price=price,
                text=text,
                timeInForce='GoodTillCancel',
            ).result()
        return response

    def limit_chase(self, oq, max_chase=3.0, failsafe=False, double_check=False):
        """"
        Attempt to fill a limit order (to earn the rebate and avoid paying the market fee) by chasing the order up the
        book - post a limit order, monitor ticker, and amend order to current ask/bid price. Ideally run this on a
        server with low latency (such as aws ireland) so that your order gets amended as quickly as possible when the
        price changes, giving it priority and thus making it more likely to be filled.
        @param oq: order quantity
        @param max_chase: max number in dollars to chase the order before giving up
        @param failsafe: if true and we cannot fill the order as limit, send a market order
        """
        ret = self.send_order(oq=oq, ot='limit', price=None)
        order_id = ret[0]['orderID']
        last_price = ret[0]['price']
        side = ret[0]['side']
        max_chase_buy = float(last_price) + float(max_chase)
        max_chase_sell = float(last_price) - float(max_chase)
        avg = last_price
        time.sleep(1)
        self.logger.info(
            f'Chasing {side} order {order_id}, order_price: {avg}, last_price: {last_price}, '
            f'current price: {last_price} max chase: {max_chase_buy}')
        count = 0
        while True:
            count += 1
            o = self.ws_orders(order_id)
            if o:
                if side == 'Buy':
                    if double_check:
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        _price = quote['buy']
                    else:
                        _price = self.ws.get_ticker()['buy']
                    if float(_price) <= float(max_chase_buy):
                        if float(last_price) < float(_price):
                            self.logger.info(f'Amending order {order_id} to price {_price}')
                            ret = self.client.Order.Order_amend(orderID=order_id, price=_price).result()
                            self.logger.info(ret)
                            last_price = _price
                        else:
                            self.logger.debug(f'Sleeping, order_price: {last_price}, current price: {_price}')
                            if double_check:
                                time.sleep(0.5)

                    else:
                        if failsafe:
                            self.logger.info(f'Order {order_id} exceeded max chase. Placing a market order.')
                            self.client.Order.Order_cancel(orderID=order_id).result()
                            self.send_order(oq, 'market', text='OrderChase Market Failsafe')
                        else:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, giving up.')
                            self.client.Order.Order_cancel(orderID=order_id).result()
                        break
                elif side == 'Sell':
                    if double_check:
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        _price = quote['sell']
                    else:
                        _price = self.ws.get_ticker()['sell']
                    if float(_price) >= float(max_chase_sell):
                        if float(last_price) > float(_price):
                            self.logger.info(f'Amending order {order_id} to price {_price} ')
                            ret = self.client.Order.Order_amend(orderID=order_id, price=_price).result()
                            self.logger.info(ret)
                            last_price = _price
                        else:
                            self.logger.debug(f'Sleeping, order_price: {last_price}, current price: {_price}')
                            if double_check:
                                time.sleep(0.5)

                    else:
                        if failsafe:
                            self.logger.info(f'Order {order_id} exceeded max chase. Placing a market order.')
                            self.client.Order.Order_cancel(orderID=order_id).result()
                            self.send_order(oq, 'market', text='OrderChase Market Failsafe')
                        else:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, giving up.')
                            self.client.Order.Order_cancel(orderID=order_id).result()
                        break
            else:
                time.sleep(0.5)
                if o:
                    self.logger.info(f'{side} Order manually Canceled!')
                self.logger.info('Order Filled')
                break

    def trailing_stop_pct(self, offset=0.33, ts_o_type='market', tschase=False, max_chase=None):
        """
        Like trailing_stop, but offset represented as a percentage between the entry +/- current price rather than a
        static dollar value
        @param offset: percentage represented like 0.33 = 30% to trail stop loss
        @param ts_o_type:
        @param tschase:
        @param max_chase:
        @return:
        """


        #  rpnl = float(r) * 0.00000001
        #  bal = float(self.get_balance()) * 0.00000001

        while True:
            pos = self.get_position()
            entry_price = pos['avgEntryPrice']
            #  last_price = self.ws.get_ticker()['last']
            qty = pos['currentQty']
            (r, u, b) = self.get_pnl()
            upnl = float(u) * 0.00000001
            bal = float(b) * 0.00000001
            if u > 0.0:
                self.logger.info(f'Trailing stop triggered: UPNL {upnl} BAL {bal}')
                break
            else:
                self.logger.info('No unrealized PNL, waiting ... ')
                time.sleep(3)
        if qty > 0:
            # long position, so this will be a sell stop
            sell_price = self.ws.get_ticker()['sell']
            offset_price = self.rounded_price(sell_price - (float(offset) * (sell_price - entry_price)), self.symbol)
            text = f'Trailing sell stop for long position, type {ts_o_type}'
            qty = qty * -1
            side = 'Sell'
            self.logger.info(
                f'Trailing Stop for long position of entry price: {entry_price} triggered: offset price {offset_price}'
                f' current price: {[sell_price]}')
        else:
            # short position, so this will be a buy stop
            buy_price = self.ws.get_ticker()['buy']
            offset_price = self.rounded_price(buy_price - float(offset) * (buy_price - entry_price), self.symbol)
            text = f'Trailing buy stop for short position, type {ts_o_type}'
            qty = qty * -1
            side = 'Buy'
            self.logger.info(
                f'Trailing Stop for short position of entry price: {entry_price} triggered: offset price {offset_price}'
                f' current price: {[buy_price]}')

        iteration = 0
        while True:

            if side == "Sell":
                sell_price = self.ws.get_ticker()['sell']
                offset_pct = self.rounded_price((sell_price - entry_price) * offset, self.symbol)
                if (float(sell_price) - float(offset_pct)) > float(offset_price):
                    offset_price = self.rounded_price(sell_price - (float(offset) * (sell_price - entry_price)), self.symbol)
                    self.logger.info("New high observed: %.8f Updating stop loss to %.8f" % (sell_price, offset_price))

                elif float(sell_price) < float(offset_price):
                    sell_price = self.ws.get_ticker()['sell']
                    if tschase:
                        self.logger.info(f'Chasing sell order ... max chase: {max_chase}')
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, sell_price,
                                                                                                 offset_price))
                        chaser = threading.Thread(target=self.limit_chase, args=(qty, max_chase, True))
                        chaser.start()
                    else:
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, sell_price,
                                                                                                 offset_price))
                        ret = self.send_order(oq=qty, ot=ts_o_type, text=text)
                        self.logger.debug(ret)

                    self.triggered = False
                    break


            if side == "Buy":
                buy_price = self.ws.get_ticker()['buy']
                offset_pct = self.rounded_price((entry_price - buy_price) * offset, self.symbol)
                if (float(buy_price) + float(offset_pct)) < float(offset_price):
                    offset_price = self.rounded_price(buy_price - float(offset) * (buy_price - entry_price))

                    self.logger.info("New low observed: %.8f Updating stop loss to %.8f" % (buy_price, offset_price))

                elif float(buy_price) > float(offset_price):
                    buy_price = self.ws.get_ticker()['buy']
                    if tschase:
                        self.logger.info(f'Chasing buy order ... max chase: {max_chase}')
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, buy_price,
                                                                                                 offset_price))
                        chaser = threading.Thread(target=self.limit_chase, args=(qty, max_chase, True))
                        chaser.start()
                    else:
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, buy_price,
                                                                                                 offset_price))
                        ret = self.send_order(oq=qty, ot=ts_o_type, text=text)
                        self.logger.debug(ret)

                    self.triggered = False
                    break


    def trailing_stop(self, offset=25, ts_o_type='market', tschase=False, max_chase=None):
        """
         Place a trailing stop order to ensure profit is taken from current position,
         Stop direction determined by current position, so there is no need to pass a negative offset, but
         if the user does then we correct it by `offset * -1`
        :param offset: integer representing how many dollars to trail the stop behind the current position
        """

        pos = self.get_position()
        entry_price = pos['avgEntryPrice']
        qty = pos['currentQty']
        self.logger.info('Trailing stop triggered')
        if qty > 0:
            # long position, so this will be a sell stop
            buy_price = self.ws.get_ticker()['sell']
            offset_price = float(buy_price) - float(offset)
            text = f'Trailing sell stop for long position, type {ts_o_type}'
            qty = qty * -1
            side = 'Sell'
            self.logger.info(
                f'Trailing Stop for long position of entry price: {entry_price} triggered: offset price {offset_price}'
                f' current price: {[buy_price]}')
        else:
            # short position, so this will be a buy stop
            buy_price = self.ws.get_ticker()['buy']
            offset_price = float(buy_price) + float(offset)
            text = f'Trailing buy stop for short position, type {ts_o_type}'
            qty = qty * -1
            side = 'Buy'
            self.logger.info(
                f'Trailing Stop for short position of entry price: {entry_price} triggered: offset price {offset_price}'
                f' current price: {[buy_price]}')

        while True:
            if side == "Sell":
                sell_price = self.ws.get_ticker()['sell']
                if (float(sell_price) - float(offset)) > float(offset_price):
                    offset_price = float(sell_price) - float(offset)
                    self.logger.info("New high observed: %.8f Updating stop loss to %.8f" % (sell_price, offset_price))
                elif float(sell_price) <= float(offset_price):
                    sell_price = self.ws.get_ticker()['sell']
                    if tschase:
                        self.logger.info(f'Chasing sell order ... max chase: {max_chase}')
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, sell_price,
                                                                                                 offset_price))
                        chaser = threading.Thread(target=self.limit_chase, args=(qty, max_chase, True))
                        chaser.start()
                    else:
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, sell_price,
                                                                                                 offset_price))
                        ret = self.send_order(oq=qty, ot=ts_o_type, text=text)
                        self.logger.debug(ret)

                    self.triggered = False
                    break

            if side == "Buy":
                buy_price = self.ws.get_ticker()['buy']
                if (float(buy_price) + float(offset)) < float(offset_price):
                    offset_price = float(buy_price) + float(offset)
                    self.logger.info("New low observed: %.8f Updating stop loss to %.8f" % (buy_price, offset_price))
                elif float(buy_price) >= float(offset_price):
                    buy_price = self.ws.get_ticker()['buy']
                    if tschase:
                        self.logger.info(f'Chasing buy order ... max chase: {max_chase}')
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, buy_price,
                                                                                                 offset_price))
                        chaser = threading.Thread(target=self.limit_chase, args=(qty, max_chase, True))
                        chaser.start()
                    else:
                        self.logger.info("Sell triggered: %s | Price: %.8f | Stop loss: %.8f" % (ts_o_type, buy_price,
                                                                                                 offset_price))
                        ret = self.send_order(oq=qty, ot=ts_o_type, text=text)
                        self.logger.debug(ret)

                    self.triggered = False
                    break

    def percentage(self, part, whole):
        return 100 * float(part) / float(whole)

    def auto_stop(self, symbol='XBTUSD', stop_loss=0.01, enable_trailing_stop=0.01, trail_offset=25.0,
                  use_ai_calc=False):
        """
        Automatic Stop Loss & Trailing Stop For Open Position
        @param symbol: override instrument (redundant)
        @param stop_loss: Set a stop loss at 30% (default) above/below entry price
        @param enable_trailing_stop: Start trailing stop tracking at 40% above/below (default) entry price
        @param trail_offset: Close position if price drops by this amount of dollars
        @param use_ai_calc: Recalculate offset based on a percentage of urealized PNL rather than a static dollar value.
        @return: none
        """
        oid = None
        open_position = False
        count = 0
        high = 0
        diff = 0
        rounds = 0
        dymamic_ts_offset = 0.0
        while True:



            rounds += 1
            posQty = self.get_position()['openingQty'] + self.get_position()['execQty']
            if posQty == 0:
                count += 1
                if open_position and oid:
                    self.client.Order.Order_cancel(orderID=oid).result()
                    open_position = False
                if count == 10:
                    self.logger.info('No position open.')
                    count = 0
                time.sleep(1)
            else:
                if count == 10:
                    self.logger.info(pretty_text(f'AutoStop Running ... Cycle: {rounds}'))
                    count = 0
                open_position = True

                ts = timestamp()
                (r, u, b) = self.get_pnl()
                r = float(r) * 0.00000001
                u = float(u) * 0.00000001
                bal = b * 0.00000001
                entry_price = self.get_position()['avgEntryPrice']
                last_price = self.ws.get_ticker()['last']
                if last_price > high:
                    high = last_price




                self.logger.info(Fore.MAGENTA + f'[ ' + f'Params: {stop_loss}|{enable_trailing_stop} | {trail_offset}] | '
                                 + f'[ High: {high}|Diff: {diff}' + Fore.RED + ' ]')
                self.logger.info(Fore.RED + f'[ Unrealized PNL: {u}' + Style.RESET_ALL + ' | ' + Fore.GREEN +
                                 f'Realized PNL: {r} ' + Style.RESET_ALL + ' | ' + Fore.BLUE + f'Balance: {bal}'
                                 + Fore.RED + ' ]')
                self.logger.info(pretty_text(
                    f'{ts}, Position: {posQty} | Entry Price: {entry_price}'))

                if posQty > 0:  # long
                    stop_loss_price = entry_price - (entry_price * (1 * stop_loss))
                    trailing_stop_price = entry_price + (entry_price * (1 * enable_trailing_stop))
                    diff = float(trailing_stop_price) - float(last_price)
                    current_price = self.ws.get_ticker()['buy']
                    if current_price <= stop_loss_price:
                        rest_failsafe = self.get_quote()['bid']
                        if rest_failsafe <= stop_loss_price:
                            stopQty = posQty * -1
                            self.logger.info(f'Closing position! Current price {current_price} <= Stop Loss Price {stop_loss_price}')
                            self.send_order(oq=stopQty, ot='market', text='bmcli LONG SL.')
                else:  # elif posQty < 0:  # short
                    stop_loss_price = entry_price + (entry_price * (1 * stop_loss))
                    trailing_stop_price = entry_price - (entry_price * (1 * enable_trailing_stop))
                    diff = float(last_price) - float(trailing_stop_price)
                    current_price = self.ws.get_ticker()['sell']
                    if current_price >= stop_loss_price:
                        rest_failsafe = self.get_quote()['ask']
                        if rest_failsafe >= stop_loss_price:
                            stopQty = posQty * -1
                            self.logger.info(f'Closing position! Current price {current_price} >= Stop Loss Price {stop_loss_price}')
                            self.send_order(oq=stopQty, ot='market', text='bmcli SHORT SL.')
                self.logger.info(pretty_text(f'Stop Loss: {stop_loss_price} | Current Price: {last_price} | Trailing Stop: '
                     f'{trailing_stop_price}'))

                """open_orders = self.rest_open_order()
                # stop loss
                has_stop = False
                for order in open_orders:
                    if order['ordType'] == 'Stop' and order['symbol'] == symbol:
                        oid = order['orderID']
                        if float(order['orderQty']) == float(posQty) or float(order['orderQty']) == (float(posQty * -1)):
                            has_stop = True
                        else:
                            self.client.Order.Order_cancel(orderID=oid).result()

                if not has_stop:
                    stopQty = posQty * -1
                    stop_loss_price = self.rounded_price(stop_loss_price, symbol)
                    self.logger.info('Setting a stop loss ...')
                    self.send_order(oq=stopQty, ot='Stop', price=None, stopPx=stop_loss_price)"""

                # AI Calc
                dymamic_ts_offset = None
                # TODO: implement
                if use_ai_calc:
                    pnl = self.get_raw()
                    mgn = pnl['maintMargain']
                    upn = pnl['unrealisedPnl']
                    current_pct = self.percentage(upn, mgn)
                    target_pct = posQty * 1 * (1/entry_price - 1/trailing_stop_price)
                    if current_pct > enable_trailing_stop:
                        if upn >= mgn:
                            self.logger.info('Unrealized PNL covers margain, initializing trailing stop!')
                            offset_price = float(last_price) - float(trail_offset)
                            ts = threading.Thread(target=self.trailing_stop, args=(trail_offset,))
                            ts.start()
                    if current_pct >= target_pct:
                        pass


                # trailing stop
                if not self.triggered:
                    if posQty > 0:
                        price = self.ws.get_ticker()['sell']
                        if float(price) >= float(trailing_stop_price):
                            offset_price = float(price) - float(trail_offset)
                            self.logger.info(f'Trailing Stop Triggered for LONG position: Offset {offset_price}')
                            ts = threading.Thread(target=self.trailing_stop, args=(trail_offset,))
                            ts.start()
                            self.triggered = True
                    if posQty < 0:
                        price = self.ws.get_ticker()['buy']
                        if float(price) <= float(trailing_stop_price):
                            offset_price = float(price) - float(trail_offset)
                            self.logger.info(f'Trailing Stop Triggered for SHORT: Offset {offset_price}')
                            ts = threading.Thread(target=self.trailing_stop, args=(trail_offset,))
                            ts.start()
                            self.triggered = True
            time.sleep(10)

    def auto_stop_multi(self, symbols=None, stop_loss=0.1, enable_trailing_stop=0.01, trail_offset_interval=3.0):
        """
        #TODO: finish implementing
        @param symbols:
        @param stop_loss:
        @param enable_trailing_stop:
        @param trail_offset_interval:
        @return:
        """

        if symbols is None:
            symbols = []
        else:

            try:
                for s in symbols:
                    self.logger.info(f'Started a thread for symbol {s}')
                    if s == 'ETHUSD':
                        trail_offset = trail_offset_interval * 0.05
                    elif s == 'XBTUSD':
                        trail_offset = trail_offset_interval * 0.5
                    else:
                        self.logger.error(f'Unsupported symbol: {s}')
                        return False

                    s = threading.Thread(target=self.auto_stop,
                                           args=(s, stop_loss, enable_trailing_stop, trail_offset,))

                    s.start()
            except KeyboardInterrupt:
                for s in symbols:
                    s.join()

    def process_incoming(self, msg):
        debug = True
        if debug:
            print(msg)
            return
        msg = msg.split(' ')
        if msg[0] == 'get_balance':
            self.get_balance()
        if msg[0] == 'get_position':
            self.get_position()



    #########################################




    def check_order_book(self, direction):
        print("Checking OrderBook...")
        obk = self.ws.market_depth()
        obk_bids = obk[0]['bids'][0:5]
        obk_asks = obk[0]['asks'][0:5]
        # print("Bids:", obk_bids)
        # print("Asks:", obk_asks)
        obk_buy_cum = 0
        obk_sell_cum = 0
        for obk_bid_unit in obk_bids:
            obk_buy_cum += obk_bid_unit[1]
        for obk_ask_unit in obk_asks:
            obk_sell_cum += obk_ask_unit[1]
        print("Sell Side: %s - Buy Side: %s" % (str(obk_sell_cum), str(obk_buy_cum)))
        if direction == 1 and obk_buy_cum > obk_sell_cum * 10:
            print("Go Buy !")
            return obk[0]['bids'][1][0]
        if direction == 0 and obk_sell_cum > obk_buy_cum * 10:
            print("Go Sell !")
            return obk[0]['asks'][1][0]
        return 0

    def covering_fee(self, init, current, direction):
        if direction == 'buy':
            target = init + (init / 100 * 0.15)
            if current > target:
                return True
        if direction == 'sell':
            target = init - (init / 100 * 0.15)
            if current < target:
                return True
        return False

    def fire_buy(self, departure):
        counter = 0
        print("Balance before:", self.ws.wallet_balance())
        '''launch_order(definition='stop_limit', direction='buy',
                     price=departure, stoplim=matrix_bmex_ticker[1], size=pos_size)'''
        '''launch_order(definition='stop_limit', direction='buy',
                     price=matrix_bmex_ticker[1], stoplim=departure, size=pos_size)'''
        self.launch_order(definition='market', direction='buy', size=self.pos_size)
        # launch_order(definition='limit', direction='buy', price=departure, size=pos_size)
        while self.ws.open_positions() == 0:
            time.sleep(1)
            counter += 1
            if counter >= 120:
                self.client.Order.Order_cancelAll().result()
                return 0
            if self.ws.open_stops() == 0:
                return 0
            continue
        print("BUY @", matrix_bmex_ticker[1])
        print("Balance - Step 1 of 2:", self.ws.wallet_balance())
        buyPos = 1
        buyPos_init = self.ws.get_instrument()['askPrice']
        buyPos_working_cached = buyPos_init
        ts_cached = [None]
        tick_buy_count = 0
        buyPos_final = 0
        trailing = False
        sl_ord_number = 0
        while buyPos > 0:
            datetime_cached = self.ws.get_instrument()['timestamp']
            dt2ts = dt.strptime(datetime_cached, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc).timestamp()
            matrix_bmex_ticker[0] = int(dt2ts * 1000)
            matrix_bmex_ticker[1] = self.ws.get_instrument()['askPrice']
            matrix_bmex_ticker[2] = self.ws.get_instrument()['bidPrice']
            if ts_cached != matrix_bmex_ticker[0]:
                tick_buy_count += 1
                ts_cached = matrix_bmex_ticker[0]
                if tick_buy_count >= 500 and trailing is False:
                    print("Cutting buy loss !")
                    if len(self.ws.open_stops()) != 0:
                        self.client.Order.Order_cancelAll().result()
                    if self.ws.open_positions() != 0:
                        # launch_order(definition='market', direction='sell', price=None, size=pos_size)
                        self.launch_order(definition='stop_loss', direction='sell', price=matrix_bmex_ticker[1],
                                     size=self.pos_size)
                    while self.ws.open_positions() != 0:
                        sleep(0.1)
                        continue
                    buyPos_final = matrix_bmex_ticker[2]
                    break
                if buyPos_working_cached < matrix_bmex_ticker[2] and self.ws.open_positions() != 0:
                    if len(self.ws.open_stops()) is not 0:
                        self.client.Order.Order_amend(orderID=sl_ord_number, stopPx=matrix_bmex_ticker[2]).result()
                        print("Trailing buy position to %s..." % str(matrix_bmex_ticker[2]))
                    if len(self.ws.open_stops()) is 0 and self.covering_fee(buyPos_init, matrix_bmex_ticker[2], 'buy'):
                        print("Buy stop loss to BE...")
                        sl_ord_number = self.launch_order(definition='stop_loss', direction='sell',
                                                     price=matrix_bmex_ticker[2],
                                                     size=self.pos_size)
                        trailing = True
                    if trailing is False:
                        continue
                    buyPos_working_cached = matrix_bmex_ticker[2]
                    print("Buy stop loss modified at %s..." % str(buyPos_working_cached))
                if self.ws.open_positions() == 0 and trailing is True:
                    if self.ws.open_positions() != 0:
                        print(sl_ord_number)
                        if len(self.ws.open_stops()) is not 0:
                            self.client.Order.Order_amend(orderID=sl_ord_number, orderQty=0).result()  # cancel stop order
                        self.launch_order(definition='market', direction='sell', price=None, size=self.pos_size)
                    print("Finishing buy trail...")
                    buyPos_final = matrix_bmex_ticker[2]
                    break
        walletBal = self.ws.wallet_balance()
        print("Closed @", str(buyPos_final), ". Balance:", str(walletBal))
        return walletBal

    def fire_sell(self, departure):
        counter = 0
        print("Balance before:", self.ws.wallet_balance())
        '''launch_order(definition='stop_limit', direction='sell',
                     price=departure, stoplim=matrix_bmex_ticker[2], size=pos_size)'''
        '''launch_order(definition='stop_limit', direction='sell',
                     price=matrix_bmex_ticker[2], stoplim=departure, size=pos_size)'''
        self.launch_order(definition='market', direction='sell', size=self.pos_size)
        # launch_order(definition='limit', direction='sell', price=departure, size=pos_size)
        while self.ws.open_positions() == 0:
            sleep(1)
            counter += 1
            if counter >= 120:
                self.client.Order.Order_cancelAll().result()
                return 0
            if self.ws.open_stops() == 0:
                return 0
            continue
        print("SELL @", matrix_bmex_ticker[2])
        print("Balance - Step 1 of 2:", self.ws.wallet_balance())
        sellPos = 1
        sellPos_init = self.ws.get_instrument()['bidPrice']
        sellPos_working_cached = sellPos_init
        ts_cached = [None]
        tick_sell_count = 0
        sellPos_final = 0
        trailing = False
        sl_ord_number = 0
        while sellPos > 0:
            datetime_cached = self.ws.get_instrument()['timestamp']
            dt2ts = dt.strptime(datetime_cached, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc).timestamp()
            matrix_bmex_ticker[0] = int(dt2ts * 1000)
            matrix_bmex_ticker[1] = self.ws.get_instrument()['askPrice']
            matrix_bmex_ticker[2] = self.ws.get_instrument()['bidPrice']
            if ts_cached != matrix_bmex_ticker[0]:
                tick_sell_count += 1
                ts_cached = matrix_bmex_ticker[0]
                if tick_sell_count >= 500 and trailing is False:
                    print("Cutting sell loss !")
                    if len(self.ws.open_stops()) != 0:
                        self.client.Order.Order_cancelAll().result()
                    if self.ws.open_positions() != 0:
                        # launch_order(definition='market', direction='buy', price=None, size=pos_size)
                        self.launch_order(definition='stop_loss', direction='buy', price=matrix_bmex_ticker[2],
                                     size=self.pos_size)
                    while self.ws.open_positions() != 0:
                        sleep(0.1)
                        continue
                    sellPos_final = matrix_bmex_ticker[1]
                    break
                if sellPos_working_cached > matrix_bmex_ticker[1] and self.ws.open_positions() != 0:
                    if len(self.ws.open_stops()) is not 0:
                        self.client.Order.Order_amend(orderID=sl_ord_number, stopPx=matrix_bmex_ticker[1]).result()
                        print("Trailing sell position to %s..." % str(matrix_bmex_ticker[1]))
                    if len(self.ws.open_stops()) is 0 and self.covering_fee(sellPos_init, matrix_bmex_ticker[1], 'sell'):
                        print("Sell stop loss to BE...")
                        sl_ord_number = self.launch_order(definition='stop_loss', direction='buy',
                                                     price=matrix_bmex_ticker[1],
                                                     size=self.pos_size)
                        trailing = True
                    if trailing is False:
                        continue
                    sellPos_working_cached = matrix_bmex_ticker[1]
                    print("Sell stop loss modified at %s..." % str(sellPos_working_cached))
                if self.ws.open_positions() == 0 and trailing is True:
                    if self.ws.open_positions() != 0:
                        print(sl_ord_number)
                        if len(self.ws.open_stops()) is not 0:
                            self.client.Order.Order_amend(orderID=sl_ord_number, orderQty=0).result()  # cancel stop order
                        self.launch_order(definition='market', direction='buy', price=None, size=self.pos_size)
                    print("Finishing sell trail...")
                    sellPos_final = matrix_bmex_ticker[1]
                    break
        walletBal = self.ws.wallet_balance()
        print("Closed @", str(sellPos_final), ". Balance:", str(walletBal))
        return walletBal

    def launch_order(self, definition, direction, price=None, size=None, stoplim=None):
        resulted = 0
        if definition == 'market':
            if direction == 'sell':
                size *= -1
            resulted = self.client.Order.Order_new(symbol=self.symbol, orderQty=size, ordType='Market').result()
            return resulted[0]['orderID']
        if definition == 'limit':
            if direction == 'sell':
                size *= -1
            resulted = self.client.Order.Order_new(symbol=self.symbol, orderQty=size, ordType='Limit', price=price,
                                              execInst='ParticipateDoNotInitiate, LastPrice').result()
            return resulted[0]['orderID']
        if definition == 'stop_limit':
            if direction == 'sell':
                size *= -1
            resulted = self.client.Order.Order_new(symbol=self.symbol, orderQty=size, ordType='StopLimit',
                                              execInst='LastPrice',
                                              stopPx=stoplim, price=price).result()
            return resulted[0]['orderID']
        if definition == 'stop_loss':
            if direction == 'sell':
                size *= -1
            resulted = self.client.Order.Order_new(symbol=self.symbol, orderQty=size, ordType='Stop',
                                              execInst='Close, LastPrice',
                                              stopPx=price).result()
            return resulted[0]['orderID']
        if definition == 'take_profit':
            if direction == 'sell':
                size *= -1
            resulted = self.client.Order.Order_new(symbol=self.symbol, orderQty=size, ordType='Limit',
                                              execInst='Close, LastPrice',
                                              price=price).result()
            return resulted[0]['orderID']

    def sybrain_scalper(self):
        matrix_bmex_ticker = [None] * 3
        matrix_bmex_trade = [None] * 5

        matrix_bmex_fairPrice = [None] * 10
        matrix_bmex_fairPrice_var = [None] * 10
        tick_count = 0
        tick_ok = False

        pos_taken = 0
        #global matrix_bmex_ticker
        #global matrix_bmex_trade
        #global matrix_bmex_fairPrice
        #global matrix_bmex_fairPrice_var
        #global pos_taken
        #global tick_count
        #global tick_ok
        fP_value_sum = 0
        fP_var_value_sum = 0
        fP_var_value_av = 0
        fairPrice_var_actual = 0
        results = 0
        p_verdict = 0
        datetime_minute_cached = None
        ts_cached = [None]
        fP_cached = [None] * 2
        while not self.ws.exited:
            try:
                if datetime_minute_cached != dt.now().minute:
                    time_starter = dt.utcnow() - timedelta(minutes=750)
                    # print(time_starter)
                    data = self.client.Trade.Trade_getBucketed(symbol=self.symbol, binSize="1m", count=750,
                                                          startTime=time_starter).result()
                    df = pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume', 'Adj Close'])
                    j = 0
                    for i in data[0]:
                        df.loc[j] = pd.Series({'Date': i['timestamp'], 'Open': i['open'], 'High': i['high'],
                                               'Low': i['low'], 'Close': i['close'], 'Volume': i['volume'],
                                               'Adj Close': i['close']})
                        j += 1
                    df = df[::-1]
                    df.to_csv(r'pair_m1.csv', index=False)
                    print('Launching Machine learning Module...')
                    start_ts = (dt.utcnow() + timedelta(minutes=0)).strftime("%Y-%m-%d %H:%M:00")
                    end_ts = (dt.utcnow() + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:00")
                    print('Start:', start_ts, '/ End:', end_ts)
                    p = Main(['pair_m1.csv', start_ts, end_ts, 'm'])
                    p_open = p.loc[p.shape[0] - 1, 'Open']
                    p_close = p.loc[p.shape[0] - 1, 'Close']
                    p_verdict = p_close - p_open
                    if p_verdict > 0:
                        print('Machine learning : UP !')
                    if p_verdict < 0:
                        print('Machine learning : DOWN !')
                    datetime_minute_cached = dt.now().minute
                datetime_cached = self.ws.get_instrument()['timestamp']
                dt2ts = dt.strptime(datetime_cached, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc).timestamp()
                matrix_bmex_ticker[0] = int(dt2ts * 1000)  # (dt2ts - dt(1970, 1, 1)) / timedelta(seconds=1000)
                matrix_bmex_ticker[1] = self.ws.get_instrument()['askPrice']
                matrix_bmex_ticker[2] = self.ws.get_instrument()['bidPrice']
                if ts_cached != matrix_bmex_ticker[0] and fP_cached[0] != self.ws.get_instrument()['fairPrice']:
                    ts_cached = matrix_bmex_ticker[0]
                    fP_cached[1] = fP_cached[0]
                    fP_cached[0] = self.ws.get_instrument()['fairPrice']
                    if fP_cached[0] is not None and fP_cached[1] is not None:
                        matrix_bmex_fairPrice_var[tick_count] = (fP_cached[0] - fP_cached[1]) / 100
                        fairPrice_var_actual = matrix_bmex_fairPrice_var[tick_count]
                        tick_count += 1
                    if tick_count >= 10:
                        tick_count = 0
                        if tick_ok is False:
                            tick_ok = True
                            print('Caching Complete !')
                    if tick_ok is True:
                        fP_var_value_sum = 0
                        for fP_var_value in matrix_bmex_fairPrice_var:
                            fP_var_value_sum += fP_var_value
                        fP_var_value_av = fP_var_value_sum / 10
                        print(
                            "Average Fair Price Variation: %s - Last Variation: %s - Last Fair Price: %s - Position Taken: %s - Balance: %s" %
                            (
                            str(fP_var_value_av), str(fairPrice_var_actual), str(self.ws.get_instrument()['fairPrice']),
                            str(pos_taken), str(self.ws.wallet_balance())))
                        if fP_var_value_av > 0 and fairPrice_var_actual > fP_var_value_av * 2 and p_verdict > 0:
                            buy_departure = self.check_order_book(1)
                            if buy_departure != 0:
                                results = self.fire_buy(buy_departure)
                                if results == 0:
                                    print("Resetting...")
                                else:
                                    print("Total Balance:", str(results))
                                if results != 0:
                                    pos_taken += 1
                                tick_ok = False
                                tick_count = 0
                        if fP_var_value_av < 0 and fairPrice_var_actual < fP_var_value_av * 2 and p_verdict < 0:
                            sell_departure = self.check_order_book(0)
                            if sell_departure != 0:
                                results = self.fire_sell(sell_departure)
                                if results == 0:
                                    print("Resetting...")
                                else:
                                    print("Total Balance:", str(results))
                                if results != 0:
                                    pos_taken += 1
                                tick_ok = False
                                tick_count = 0

            except Exception as e:
                print(str(e))
                self.ws.exit()
                print(" This is the end !")

            except KeyboardInterrupt:
                self.ws.exit()
                print(" This is the end !")

    #def mqtt(self):
    #    mq.run()

            
