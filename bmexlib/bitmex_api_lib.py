import threading
import bitmex
import time
import json
from exchange_lib.bitmex_ws import BitMEXWebsocket
import logging
import datetime
from colorama import Fore, Back, Style, init
logging.basicConfig(level=logging.INFO, format=(Fore.BLUE + '[+] ' + Style.RESET_ALL + '%(message)s '))
init(autoreset=True)

def timestamp():
    """
    Get current time
    @return: string timestamp
    """
    ts = time.time()
    st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    return str(f'[{st}]')


class BitmexApiTool:
    """
    Bitmex Functions Library
    """

    def __init__(self, symbol='XBTUSD', api_key=None, api_secret=None, test_net=False, require_ws=False):
        self.triggered = False
        self.symbol = symbol
        self.api_key = api_key
        self.api_secret = api_secret
        self.test_net = test_net
        self.require_ws = require_ws
        self.logger = logging.getLogger(__name__)
        self.ws = None

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

    def send_order(self, oq, ot, price=None, stopPx=0.0, pegOffsetValue=0, text='bmx_api_tool'):
        if price is None:
            if self.ws:
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
                    if count == 100000:
                        self.logger.info(
                            f'Chasing buy order {order_id}, order_price: {avg}, last_price: {last_price}, current price: '
                            f'{_price} max chase: {max_chase_buy}')
                        count = 0
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
                            self.send_order(oq, 'market', text='OrderChase Market Failsafe')
                        else:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, giving up.')
                        break
                elif side == 'Sell':
                    if double_check:
                        quote = self.get_quote()
                        self.logger.info('Bid: {} Ask: {}'.format(quote['bidPrice'], quote['askPrice']))
                        _price = quote['sell']
                    else:
                        _price = self.ws.get_ticker()['sell']
                        if count == 100000:
                            self.logger.info(
                                f'Chasing sell order {order_id}, order_price: {avg}, last_price: {last_price}, current price: '
                                f'{_price} max chase: {max_chase_sell}')
                            count = 0
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
                            self.send_order(oq, 'market', text='OrderChase Market Failsafe')
                        else:
                            self.logger.info(f'Price {_price} exceeded max chase {max_chase_buy}, giving up.')
                        break
            else:
                self.logger.info('Order Filled')
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

    def auto_stop(self, symbol='XBTUSD', stop_loss=0.01, enable_trailing_stop=0.01, trail_offset=25.0):
        """
        Automatic Stop Loss & Trailing Stop For Open Position
        @param stop_loss: Set a stop loss at 30% (default) above/below entry price
        @param enable_trailing_stop: Start trailing stop tracking at 40% above/below (default) entry price
        @param trail_offset: Close position if price drops by this amount of dollars
        @return: none
        """

        open_position = False
        count = 0
        high = 0
        diff = 0
        while True:

            posQty = self.get_position()['openingQty'] + self.get_position()['execQty']
            if posQty == 0:
                count += 1
                if open_position:
                    self.client.Order.Order_cancelAll(symbol=symbol).result()
                    open_position = False
                if count == 10:
                    self.logger.info('No position open.')
                    count = 0
                time.sleep(1)
            else:

                open_position = True
                ts = timestamp()
                entry_price = self.get_position()['avgEntryPrice']
                last_price = self.ws.get_ticker()['last']
                if last_price > high:
                    high = last_price


                self.logger.info(Fore.RED + '[ ' + Style.RESET_ALL +
                                    f'Autostop Running: Params: {stop_loss}|{enable_trailing_stop}|{trail_offset} '
                                    f'High: {high}, Diff: {diff}'
                                    + Fore.RED + ' ]' + Style.RESET_ALL)
                self.logger.info(
                    f'Time: {ts}, Position: {posQty}, Entry Price: {entry_price}, Current Price: {last_price}')
                if posQty > 0:  # long
                    stop_loss_price = entry_price - (entry_price * (1 * stop_loss))
                    trailing_stop_price = entry_price + (entry_price * (1 * enable_trailing_stop))
                else:  # elif posQty < 0:  # short
                    stop_loss_price = entry_price + (entry_price * (1 * stop_loss))
                    trailing_stop_price = entry_price - (entry_price * (1 * enable_trailing_stop))
                self.logger.info(f'Stop Loss: {stop_loss_price}, Trailing Stop: {trailing_stop_price}')

                open_orders = self.rest_open_order()
                # stop loss
                has_stop = False
                for order in open_orders:
                    print(order)
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
                    self.send_order(oq=stopQty, ot='Stop', price=None, stopPx=stop_loss_price)
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
