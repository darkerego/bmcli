#!/usr/bin/env python3
################################
# Bitmex-Cli ~ Darkerego 2019-2020

"""
BitMex API TOOL -- Python3 powered CLI tool to make manual bitmex trading easier.
Features include: get account balance and position, create a new order,
"""
import argparse
from time import sleep

from bmexlib.bitmex_api_lib import BitmexApiTool
from bmexlib.conf import testnet, api_key, api_secret, keys
from bmexlib.colorprint import ColorPrint


class BitmexLogic:
    """
    Functions for everything the frontend does!
    """
    def __init__(self, symbol='XBTUSD', require_ws=False):

        self.symbol = symbol
        self.require_ws = require_ws
        if self.require_ws:
            self.api = BitmexApiTool(symbol=self.symbol, api_key=api_key, api_secret=api_secret, test_net=testnet,
                                     require_ws=True)
        else:
            self.api = BitmexApiTool(symbol=self.symbol, api_key=api_key, api_secret=api_secret, test_net=testnet,
                                     require_ws=False)

    def monitor_account(self, symbol='XBTUSD'):

        while True:
            try:

                bal = self.api.get_balance()
                pos = self.api.get_position()
                pnl = self.api.get_raw()
                cp.green(f'Instrument: {symbol}')
                cp.green(f'Balance: {bal}')
                pos_qty = pos['openingQty'] + pos['execQty']
                cp.green(f'Position: {pos_qty}')
                if args.verbose:
                    cp.cyan(f'Raw: {pnl}')
                prev_realized = pnl['prevRealisedPnl']
                realized = pnl['realisedPnl']
                unrealized = pnl['unrealisedPnl']
                cp.red(f'Unrealized PNL: {unrealized}')
                cp.green(f'Realized PNL: {realized}')
                cp.yellow(f'Previous PNL: {prev_realized}')
                cp.blue('-------------------------------------------')
            except KeyboardInterrupt:
                cp.red('Exiting...')
            else:
                sleep(5)

    def balance(self):
        bal = self.api.get_balance()
        if bal == 0:
            cp.red('Zero balance available!')
        else:
            cp.green(f'Balance: {bal}')

    def position(self):
        pos = self.api.get_position()

        if pos == 0:
            cp.red(f'No position for {self.symbol}')
            exit(0)
        pos_qty = pos['openingQty'] + pos['execQty']
        cp.green(f'Position: {pos_qty}')

    def pnl(self, _symbol):
        pnl = self.api.get_raw()
        prev_realized = pnl['prevRealisedPnl']
        realized = pnl['realisedPnl']
        unrealized = pnl['unrealisedPnl']
        cp.green(f'Instrument: {_symbol}: Unrealized PNL: {unrealized}, Realized PNL: {realized}, Prev_realized: '
                 f'{prev_realized}')

    def create_order(self):
        cp.green(f'Creating new order of type {args.new_order}...')
        api = BitmexApiTool(symbol=self.symbol, api_key=api_key, api_secret=api_secret, test_net=testnet,
                            require_ws=False)
        cp.cyan(api.send_order(oq=args.quantity, ot=args.new_order, price=args.price, stopPx=args.stop_px,
                               pegOffsetValue=args.pegoffsetvalue))

    def chase_order(self):
        cp.green(f'Chasing order of qty {args.chase[0]}')
        self.api.limit_chase(oq=args.chase[0], max_chase=args.max_chase, failsafe=args.failsafe, double_check=False)

    def trail(self):
        if args.chase_ts is not None:
            max_chase_ts = float(args.chase_ts[0])
        else:
            max_chase_ts = None
        offset = float(args.trailing_stop_order[0])
        cp.green(f'Initializing Trailing Stop with offset: {offset}, Order Chase: {args.cts}')
        api = BitmexApiTool(symbol=args.symbol, api_key=api_key, api_secret=api_secret, test_net=testnet,
                            require_ws=True)
        api.trailing_stop(offset=offset, ts_o_type=args.ts_type, tschase=args.cts, max_chase=max_chase_ts)

    def auto_stop_poll(self):
        stop_loss = args.autostop[0]
        enable_ts = args.autostop[1]
        trail_offset = args.autostop[2]
        cp.yellow(f'AutoStop: Stop Loss {stop_loss}, Enable Trailing Stop: {enable_ts}, Trail Offset: {trail_offset}')
        api = BitmexApiTool(symbol=self.symbol, api_key=api_key, api_secret=api_secret, test_net=testnet,
                            require_ws=True)
        api.auto_stop(symbol=args.symbol, stop_loss=stop_loss, enable_trailing_stop=enable_ts,
                      trail_offset=trail_offset)


def parse_args():
    """
    Argparse Function
    @return: argparse object
    """
    parser = argparse.ArgumentParser(prog='bitmex-cli', usage='Please see the README.md file on '
                                                              'https://github.com/isdrupter/bmcli')
    rest_api = parser.add_argument_group('Rest API Functions')
    general_opts = parser.add_argument_group('General Options')
    general_opts.add_argument('-s', '--symbol', dest='symbol', help='Symbol of instrument', default='XBTUSD')
    general_opts.add_argument('-k', '--keys', dest='use_curr_keys', default=True,
                              help='Use instrument dict from conf.py to determine'
                              'which api keys to use', action='store_true')
    general_opts.add_argument('-v', '--verbose', dest='verbose', action='store_true')
    rest_api.add_argument('-b', '--balance', dest='balance', action='store_true', help='Get Balance')
    rest_api.add_argument('-p', '--position', dest='position', action='store_true', help='Get Position')
    rest_api.add_argument('-P', '--pnl', dest='pnl', action='store', nargs=1, type=str,
                          help='Get Un/Realized PNL of specified symbol <--pnl XBTUSD>')
    monitor_opts = parser.add_argument_group('Various tools for monitoring trading')
    monitor_opts.add_argument('-m', '--monitor', dest='monitor_acct', action='store', nargs=1, help='Monitor account'
                                                                                                    'instrument'
                                                                                                    'activity.')
    order_opts = parser.add_argument_group('Flags for creating orders.')
    order_opts.add_argument('-o', '--order', dest='new_order', help='Place an order', type=str,
                            choices=['limit', 'market', 'post', 'stop', 'stop_limit', 'limit_if_touched'])
    order_opts.add_argument('-q', '--qty', '-oq', dest='quantity', type=float, help='Quantity for orders placed. '
                                                                                    'Use negative value to open a '
                                                                                    'short position.')
    order_opts.add_argument('--price', '-op', dest='price', type=float, default=None,
                            help='Price for limit or post orders (if required.')
    order_opts.add_argument('--stop_px', dest='stop_px', type=float, default=None, help='Stop price for stop orders.')
    order_opts.add_argument('--peg', '--pegoffsetvalue', dest='pegoffsetvalue', default=None, type=float,
                            help='PegOffsetValue for LimitIfTouched orders.')

    order_chase_opts = parser.add_argument_group('Order Chasing')
    order_chase_opts.add_argument('-c', '--chase', dest='chase', action='store', type=float, nargs=1,
                                  help='Limit Order Chase this quantity <--chase -100 -s ETHUSD>')
    order_chase_opts.add_argument('-F', '--chase_failsafe', action='store_true', dest='failsafe',
                                  help='Revert to market if max chase exceeded.')
    order_chase_opts.add_argument('-M', '--max_chase', dest='max_chase', default='1.0', type=float,
                                  help='Max limit chase in dollar value.')
    stop_opts = parser.add_argument_group('Auto/Trailing Stop Options')
    stop_opts.add_argument('-t', '--trailing_stop', dest='trailing_stop', type=float, nargs=1,
                           help='Place a trailing stop order with this offset. <-t 10.0>')
    stop_opts.add_argument('-a', '--auto_stop', dest='autostop', action='store', type=float, nargs=3,
                           help='Autostop Loss, Trailing Stop. Example -a 0.015 0.03 25 (Stop loss at 15 percent +/- '
                                'entry price, enable trailing stop at 30 percent +/- entry price, close position '
                                'when price drops 25 dollars +/- trailing stop price.) See documentation for more '
                                'details.')
    stop_opts.add_argument('-l', '--limit_order', '--limit', dest='use_limit_order', action='store_true', default=False,
                           help='Use limit orders for trailing stops. Warning: not recommended except for experienced '
                                'traders.')
    stop_opts.add_argument('-C', '--chase_ts', dest='chase_ts', action='store',
                           help='Use limit order chasing with trailing stops. Specify max chase like <-C 3.0>',
                           nargs=1, type=float)
    scalp_opts = parser.add_argument_group('Options for Experimental Scalping')
    scalp_opts.add_argument('--scalp', action='store', nargs=1, type=float, help='Experimental scalping engine')
    # scalp_opts.add_argument('-')
    return parser.parse_args()


def main():
    """
    Main logic here
    """
    global api_key, api_secret, args
    args = parse_args()  # define args
    symbol = args.symbol

    if args.use_curr_keys:
        if args.symbol == 'XBTUSD':
            api_key = keys[0][0]['XBTUSD']['key']
            api_secret = keys[0][0]['XBTUSD']['secret']
        if args.symbol == 'ETHUSD':
            api_key = keys[1][0]['ETHUSD']['key']
            api_secret = keys[1][0]['ETHUSD']['secret']
    if args.use_limit_order:
        ts_type = 'limit'
    else:
        ts_type = 'market'

    if args.chase_ts:
        cp.red(f'Warn: Limit chasing for trailing stops is enabled with max chase {args.chase_ts[0]}.')
        cts = True
    else:
        cts = False

    """
    Main functionality % logic
    """

    if args.monitor_acct:
        bmx = BitmexLogic(symbol=symbol, require_ws=False)
        bmx.monitor_account(symbol)
    if args.balance:
        bmx = BitmexLogic(symbol=symbol, require_ws=False)
        bmx.balance()
    if args.position:
        bmx = BitmexLogic(symbol=symbol, require_ws=False)
        bmx.position()
    if args.pnl:
        bmx = BitmexLogic(symbol=symbol, require_ws=False)
        _symbol = args.get_pnl[0]
        bmx.pnl(_symbol)
    if args.new_order:
        bmx = BitmexLogic(symbol=symbol, require_ws=False)
        bmx.create_order()
    if args.chase:
        bmx = BitmexLogic(symbol=symbol, require_ws=True)
        bmx.chase_order()
    if args.trailing_stop:
        bmx = BitmexLogic(symbol=symbol, require_ws=True)
        bmx.trail()
    if args.autostop:
        bmx = BitmexLogic(symbol=symbol, require_ws=True)
        bmx.auto_stop_poll()
    #if scalp:
    #    bmx = BitmexLogic(symbol=symbol, require_ws=True)


if __name__ == '__main__':
    cp = ColorPrint()
    try:
        main()
    except KeyboardInterrupt:
        cp.red(f'Caught Signal, Exiting ... ')
    except Exception as fuck:
        cp.red(f'Error: {fuck}')
    finally:
        exit()
