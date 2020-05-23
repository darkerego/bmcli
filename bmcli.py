#!/usr/bin/env python3
# Darkerego ~ 2019 - 2020
"""
BitMex API TOOL -- Python3 powered CLI tool to make manual bitmex trading easier.
Features include: get account balance and position, create a new order.
Donations are appreciated: BTC: 16XCgQyNxoYmduCxWBoVQwk8QgLw6dZ8De
"""
import argparse
from bmexlib.bitmex_api_lib import BitmexApiTool
from bmexlib.conf import *
from colorama import Fore, Style, init

init(autoreset=True)


class ColorPrint:
    """
    Colorized Output Class
    """

    def red(self, data):
        print(Fore.RED + Style.BRIGHT + '[!] ' + Style.RESET_ALL + str(data))

    def green(self, data):
        print(Fore.GREEN + Style.BRIGHT + '[+] ' + Style.RESET_ALL + str(data))

    def yellow(self, data):
        print(Fore.YELLOW + Style.BRIGHT + '[i] ' + Style.RESET_ALL + str(data))

    def blue(self, data):
        print(Fore.BLUE + Style.BRIGHT + '[+] ' + Style.RESET_ALL + str(data))

    def cyan(self, data):
        print(Fore.CYAN + Style.BRIGHT + '[*] ' + Style.RESET_ALL + str(data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', '--balance', dest='balance', action='store_true', help='Get Balance')
    parser.add_argument('-p', '--position', dest='position', action='store_true', help='Get Position')
    parser.add_argument('-o', '--order', dest='new_order', help='Place an order', type=str, choices=['limit',
                                                                                                     'market',
                                                                                                     'post', 'stop',
                                                                                                     'stop_limit',
                                                                                                     'limit_if_touched'])
    # TODO: better/more options for creating orders
    parser.add_argument('-c', '--chase', dest='chase', action='store_true', help='Limit Order Chase')
    parser.add_argument('-F', '--chase_failsafe', action='store_true', dest='failsafe',
                        help='Revert to market if max chase exceeded.')
    parser.add_argument('-M', '--max_chase', dest='max_chase', default='3.0', type=float, help='Max limit chase')
    parser.add_argument('-t', '--trailing_stop', dest='trailing_stop', type=float, nargs=1,
                        help='Place a trailing stop order with this offset.')
    parser.add_argument('-a', '--auto_stop', dest='autostop', action='store', type=float, nargs=3,
                        help='Autostop Loss, Trailing Stop. Example -a 0.015 0.03 25 (Stop loss at 15 percent +/- '
                             'entry price, enable trailing stop at 30 percent +/- entry price, close position '
                             'when price drops 25 dollars +/- trailing stop price.) See documentation for more '
                             'details.')
    parser.add_argument('-s', '--symbol', dest='symbol', help='Symbol self.of instrument', default='XBTUSD')
    parser.add_argument('-q', '--qty', dest='quantity', type=float, help='Quantity for orders placed. '
                                                                         'Use negative value to open a short position.')

    args = parser.parse_args()

    balance = args.balance
    position = args.position
    new_order = args.new_order
    chase = args.chase
    failsafe = args.failsafe
    max_chase = args.max_chase
    trailing_stop_order = args.trailing_stop
    autostop = args.autostop
    symbol = args.symbol
    quantity = args.quantity
    cp = ColorPrint()
    if balance:
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=False)
        bal = api.get_balance()
        if bal == 0:
            cp.red('Zero balance available!')
        else:
            cp.green(f'Balance: {bal}')
    if position:
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=False)
        pos = api.get_position()
        if pos == 0:
            cp.red(f'No position for {symbol}')
            exit(0)
        pos_qty = pos['openingQty'] + pos['execQty']
        cp.green(f'Position: {pos_qty}')
    if new_order:
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=False)
        cp.cyan(api.send_order(oq=quantity, ot=args.new_order))
    if chase:
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.limit_chase(oq=quantity, max_chase=max_chase, failsafe=failsafe, double_check=False)
    if trailing_stop_order:
        offset = float(trailing_stop_order[0])
        cp.green(f'Initializing Trailing Stop with offset: {offset}')
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.trailing_stop(offset=offset)
    if autostop:
        stop_loss = autostop[0]
        enable_ts = autostop[1]
        trail_offset = autostop[2]
        cp.yellow(f'AutoStop: Stop Loss {stop_loss}, Enable Trailing Stop: {enable_ts}, Trail Offset: {trail_offset}')
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.auto_stop(stop_loss=stop_loss, enable_trailing_stop=enable_ts, trail_offset=trail_offset)


if __name__ == '__main__':
    main()
