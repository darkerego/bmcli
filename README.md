#BMCLI - Bitmex Api Tool

~ Darkerego, 2019 - 2020

BTC: 16XCgQyNxoYmduCxWBoVQwk8QgLw6dZ8De

======

## About:

<p>
Bmcli is a python3 powered, command line API tool for interacting with the Bitmex 
exchange. It is intended to make manual trading easier and more profitable by 
automating some of the things that traders do all of the time and offering some 
unique features such as <i>order chasing</i> and built in trailing stop functionality 
which does not use on Bitmex's trailing stop feature -- this is because bimex's stop's 
sometimes don't execute on time or properly due to 'system overload', or whatever.
</p>

## Features:

- Create long/short limit/market/post/etc orders
- Check account balance
- Get current position
- AutoStop - Watch for new positions and automatically set a stop loss, and trigger 
a trailing stop when the price goes a user defined percentage upwards. 
- Trailing Stops - Custom python implementation of trailing stop functionality
- Limit Order Chasing - Chase your order up or down the books, amending the price 
so that it is at the top of the orderbook to ensure not paying the market fee and 
entering a position. Optionally use `chase_failsafe` to revert to a market order 
if the `max chase` variable is exceeded. 

## Install Deps:

<pre>
$ pip3 install -r requirements.txt
</pre>

## Usage:

<pre>
$ ./bmcli -h
usage: bmcli [-h] [-b] [-p]
             [-o {limit,market,post,stop,stop_limit,limit_if_touched}] [-c]
             [-F] [-M MAX_CHASE] [-t TRAILING_STOP]
             [-a AUTOSTOP AUTOSTOP AUTOSTOP] [-s SYMBOL] [-q QUANTITY]

optional arguments:
  -h, --help            show this help message and exit
  -b, --balance         Get Balance
  -p, --position        Get Position
  -o {limit,market,post,stop,stop_limit,limit_if_touched}, --order {limit,market,post,stop,stop_limit,limit_if_touched}
                        Place an order
  -c, --chase           Limit Order Chase
  -F, --chase_failsafe  Revert to market if max chase exceeded.
  -M MAX_CHASE, --max_chase MAX_CHASE
                        Max limit chase
  -t TRAILING_STOP, --trailing_stop TRAILING_STOP
                        Place a trailing stop order with this offset.
  -a AUTOSTOP AUTOSTOP AUTOSTOP, --auto_stop AUTOSTOP AUTOSTOP AUTOSTOP
                        Autostop Loss, Trailing Stop. Example -a 0.015 0.03 25
                        (Stop loss at 15 percent +/- entry price, enable
                        trailing stop at 30 percent +/- entry price, close
                        position when price drops 25 dollars +/- trailing stop
                        price.) See documentation for more details.
  -s SYMBOL, --symbol SYMBOL
                        Symbol self.of instrument
  -q QUANTITY, --qty QUANTITY
                        Quantity for orders placed. Use negative value to open
                        a short position. 

</pre>

<p>
First, edit `lib/conf.py` and add your api keys. Next, it is stronly recommended 
to activate the virtual env because I have modified the libraries to stop those 
stupid swagger client warnings:
</p>
<pre>
$ . venv/bin/activate
</pre>

###### Check Balance:

<pre>
$ ./bmcli -b
[+] Balance: 1417332
</pre>

### Sample Output

###### Get Current position

<pre>
$ ./bmcli -p -s ETHUSD
[+] Position: 2000
</pre>

###### Create Order
<pre>
./bmcli -o limit -q 100 -s XBTUSD
INFO:lib.bitmex_api_lib:quote {'symbol': 'XBTUSD', 'id': 8799047500, 'side': 'Sell', 'size': 1539179, 'price': 9525.0}
Sending buy order for 100.0 at 9525.0 , order type: limit
[*] ({'orderID': '9945cbf4-10af-9a14-1d28-419d25a7481b', 'clOrdID': '', 'clOrdLinkID': '', 'account': 'xxxxxx', 'symbol': 'XBTUSD', 'side': 'Buy', 'simpleOrderQty': None, 'orderQty': 100, 'price': 9525.0, 'displayQty': None, 'stopPx': None, 'pegOffsetValue': None, 'pegPriceType': '', 'currency': 'USD', 'settlCurrency': 'XBt', 'ordType': 'Limit', 'timeInForce': 'GoodTillCancel', 'execInst': '', 'contingencyType': '', 'exDestination': 'XBME', 'ordStatus': 'Filled', 'triggered': '', 'workingIndicator': False, 'ordRejReason': '', 'simpleLeavesQty': None, 'leavesQty': 0, 'simpleCumQty': None, 'cumQty': 100, 'avgPx': 9524.5, 'multiLegReportingType': 'SingleSecurity', 'text': 'bmx_api_tool', 'transactTime': datetime.datetime(2020, 5, 20, 23, 20, 33, 286000, tzinfo=tzutc()), 'timestamp': datetime.datetime(2020, 5, 20, 23, 20, 33, 286000, tzinfo=tzutc())}, <bravado.requests_client.RequestsResponseAdapter object at 0x7f29c6868550>)

</pre>

###### Order Chase

<pre>
$ ./bmcli -c -q 100 -M 1
INFO:exchange_lib.bitmex_ws:Connecting to wss://www.bitmex.com/realtime?subscribe=execution:XBTUSD,instrument:XBTUSD,order:XBTUSD,position:XBTUSD,quote:XBTUSD,trade:XBTUSD,margin
INFO:exchange_lib.bitmex_ws:Authenticating with API Key.
INFO:exchange_lib.bitmex_ws:Connected to WS.
INFO:exchange_lib.bitmex_ws:Got all market data. Starting.
Sending buy order for 100.0 at 9515 , order type: limit
INFO:lib.bitmex_api_lib:Chasing buy order c2e7fee0-20af-3f5d-a7b9-c22d49de2c19, order_price: 9508.0, last_price: 9508.0, current price: 9508 max chase: 9511.0
.... trunicated
INFO:lib.bitmex_api_lib:Chasing buy order c2e7fee0-20af-3f5d-a7b9-c22d49de2c19, order_price: 9508.0, last_price: 9508.0, current price: 9508 max chase: 9511.0
INFO:lib.bitmex_api_lib:Order Filled

</pre>
See <a href='https://asciinema.org/a/Ctn7upSmaIuhhJOXEBxBZMYoi'>Asciinema Recording</a> here.


###### Trailing Stop

<pre>
./bmcli -t 10
[+] Initializing Trailing Stop with offset: 10.0
INFO:exchange_lib.bitmex_ws:Connecting to wss://www.bitmex.com/realtime?subscribe=execution:XBTUSD,instrument:XBTUSD,order:XBTUSD,position:XBTUSD,quote:XBTUSD,trade:XBTUSD,margin
INFO:exchange_lib.bitmex_ws:Authenticating with API Key.
INFO:exchange_lib.bitmex_ws:Connected to WS.
INFO:exchange_lib.bitmex_ws:Got all market data. Starting.
INFO:bmexlib.bitmex_api_lib:Trailing stop triggered
INFO:bmexlib.bitmex_api_lib:Trailing Stop for long position of entry price: 9535.6155 triggered: offset price 9521.5 current price: [9531.5]
INFO:bmexlib.bitmex_api_lib:New high observed: 9533.00000000 Updating stop loss to 9523.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9538.50000000 Updating stop loss to 9528.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9539.00000000 Updating stop loss to 9529.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9540.50000000 Updating stop loss to 9530.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9545.00000000 Updating stop loss to 9535.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9546.50000000 Updating stop loss to 9536.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9547.00000000 Updating stop loss to 9537.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9550.00000000 Updating stop loss to 9540.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9560.50000000 Updating stop loss to 9550.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9562.00000000 Updating stop loss to 9552.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9567.00000000 Updating stop loss to 9557.00000000
Sending sell order for -2100 at 9553.5 , order type: market
INFO:bmexlib.bitmex_api_lib:Sell triggered | Price: 9553.50000000 | Stop loss: 9557.00000000

</pre>
<p>

[![asciicast](https://asciinema.org/a/RUySuh40ObfavX7qxw8yafRSP.svg)](https://asciinema.org/a/RUySuh40ObfavX7qxw8yafRSP)</p>


###### AutoStop

<pre>
$ ./bmcli -a 0.001 0.005 10
[i] AutoStop: Stop Loss 0.01, Enable Trailing Stop: 0.005, Trail Offset: 10.0
INFO:exchange_lib.bitmex_ws:Connecting to wss://www.bitmex.com/realtime?subscribe=execution:XBTUSD,instrument:XBTUSD,order:XBTUSD,position:XBTUSD,quote:XBTUSD,trade:XBTUSD,margin
INFO:exchange_lib.bitmex_ws:Authenticating with API Key.
INFO:exchange_lib.bitmex_ws:Connected to WS.
INFO:exchange_lib.bitmex_ws:Got all market data. Starting.
INFO:bmexlib.bitmex_api_lib:Time: 2020-05-20 20:45:33, Position: 500, Entry Price: 9535.5, Current Price: 9537.5
INFO:bmexlib.bitmex_api_lib:Stop Loss Price: 9492.3, Trailing Stop Enable: 9549.54 
INFO:bmexlib.bitmex_api_lib:Trailing stop triggered
INFO:bmexlib.bitmex_api_lib:Trailing Stop for long position of entry price: 9535.5 triggered: offset price 9521.5 current price: [9531.5]
INFO:bmexlib.bitmex_api_lib:New high observed: 9533.00000000 Updating stop loss to 9523.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9538.50000000 Updating stop loss to 9528.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9539.00000000 Updating stop loss to 9529.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9540.50000000 Updating stop loss to 9530.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9545.00000000 Updating stop loss to 9535.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9546.50000000 Updating stop loss to 9536.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9547.00000000 Updating stop loss to 9537.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9550.00000000 Updating stop loss to 9540.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9560.50000000 Updating stop loss to 9550.50000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9562.00000000 Updating stop loss to 9552.00000000
INFO:bmexlib.bitmex_api_lib:New high observed: 9567.00000000 Updating stop loss to 9557.00000000
INFO:bmexlib.bitmex_api_lib:Trailing Stop Triggered for LONG position: Offset 10.0
Sending sell order for -2100 at 9553.5 , order type: market
INFO:bmexlib.bitmex_api_lib:Sell triggered | Price: 9553.50000000 | Stop loss: 9557.00000000


</pre>

[![asciicast](https://asciinema.org/a/bOtzGkjuHNKGo5kEnAWWoOimH.svg)](https://asciinema.org/a/bOtzGkjuHNKGo5kEnAWWoOimH)
