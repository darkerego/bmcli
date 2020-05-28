#!/usr/bin/env python3
################################
# Bitmex-Cli ~ Darkerego 2019-2020

"""
BitMex API TOOL -- Python3 powered CLI tool to make manual bitmex trading easier.
Features include: get account balance and position, create a new order,
"""
import argparse
from bmexlib.bitmex_api_lib import BitmexApiTool
from bmexlib.conf import *
from bmexlib.colorprint import ColorPrint


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
    rest_api.add_argument('-b', '--balance', dest='balance', action='store_true', help='Get Balance')
    rest_api.add_argument('-p', '--position', dest='position', action='store_true', help='Get Position')
    rest_api.add_argument('-P', '--pnl', dest='pnl', action='store', nargs=1, type=str,
                          help='Get Un/Realized PNL of specified symbol <--pnl XBTUSD>')
    order_opts = parser.add_argument_group('Flags for creating orders.')
    order_opts.add_argument('-o', '--order', dest='new_order', help='Place an order', type=str,
                            choices=['limit', 'market', 'post', 'stop', 'stop_limit', 'limit_if_touched'])
    order_opts.add_argument('-q', '--qty', '-oq', dest='quantity', type=float, help='Quantity for orders placed. '
                                                                                    'Use negative value to open a short '
                                                                                    'position.')
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

    return parser.parse_args()


def main():
    """
    Main logic here
    """
    global api_key, api_secret
    args = parse_args()  # define args
    balance = args.balance
    position = args.position
    new_order = args.new_order
    price = args.price
    stop_px = args.stop_px
    pegoffsetvalue = args.pegoffsetvalue
    chase = args.chase
    chase_ts = args.chase_ts
    failsafe = args.failsafe
    max_chase = args.max_chase
    trailing_stop_order = args.trailing_stop
    autostop = args.autostop
    symbol = args.symbol
    quantity = args.quantity
    use_limit_order = args.use_limit_order
    get_pnl = args.pnl
    use_curr_keys = args.use_curr_keys
    """if use_curr_keys:
        if symbol == 'XBTUSD':
            api_key = keys[0][0]['XBTUSD']['key']
            api_secret = keys[0][0]['XBTUSD']['secret']
        if symbol == 'ETHUSD':
            api_key = keys[1][0]['ETHUSD']['key']
            api_secret = keys[1][0]['ETHUSD']['secret']"""
    if use_limit_order:
        ts_type = 'limit'
    else:
        ts_type = 'market'

    if chase_ts:
        cp.red(f'Warn: Limit chasing for trailing stops is enabled with max chase {chase_ts[0]}.')
        cts = True
    else:
        cts = False

    """
    Main functionality % logic
    """

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

    if get_pnl:
        _symbol = get_pnl[0]
        api = BitmexApiTool(symbol=_symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=False)
        pnl = api.get_raw()
        prev_realized = pnl['prevRealisedPnl']
        realized = pnl['realisedPnl']
        unrealized = pnl['unrealisedPnl']
        cp.green(f'Instrument: {_symbol}: Unrealized PNL: {unrealized}, Realized PNL: {realized}, Prev_realized: '
                 f'{prev_realized}')

    if new_order:
        cp.green(f'Creating new order of type {new_order}...')
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=False)
        cp.cyan(api.send_order(oq=quantity, ot=args.new_order, price=price, stopPx=stop_px,
                               pegOffsetValue=pegoffsetvalue))

    if chase:
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.limit_chase(oq=chase[0], max_chase=max_chase, failsafe=failsafe, double_check=False)

    if trailing_stop_order:
        if chase_ts is not None:
            max_chase_ts = float(chase_ts[0])
        else:
            max_chase_ts = None
        offset = float(trailing_stop_order[0])
        cp.green(f'Initializing Trailing Stop with offset: {offset}, Order Chase: {cts}')
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.trailing_stop(offset=offset, ts_o_type=ts_type, tschase=cts, max_chase=max_chase_ts)

    if autostop:
        stop_loss = autostop[0]
        enable_ts = autostop[1]
        trail_offset = autostop[2]
        cp.yellow(f'AutoStop: Stop Loss {stop_loss}, Enable Trailing Stop: {enable_ts}, Trail Offset: {trail_offset}')
        api = BitmexApiTool(symbol=symbol, api_key=api_key, api_secret=api_secret, test_net=testnet, require_ws=True)
        api.auto_stop(symbol=symbol, stop_loss=stop_loss, enable_trailing_stop=enable_ts, trail_offset=trail_offset)


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
