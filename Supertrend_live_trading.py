import requests
import json
import time
import pandas as pd
from datetime import datetime, timezone
import pandas_ta as ta

account_id = '101-001-29547380-004'
auth_key = '9d9ec46eb7f1847d00ad7cae2ae23bf8-95e63748ad228acf5d88954c3e75d6f9'
api_url = 'https://api-fxpractice.oanda.com/v3'

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {auth_key}',
}

trade_open = False
position_type = None
entry_price = None

def get_live_price(instrument):
    url = f"{api_url}/accounts/{account_id}/pricing"
    params = {'instruments': instrument}
    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        pricing_data = response.json()
        if 'prices' in pricing_data and len(pricing_data['prices']) > 0:
            for price in pricing_data['prices']:
                if price['instrument'] == instrument:
                    bid_price = float(price['bids'][0]['price'])
                    ask_price = float(price['asks'][0]['price'])
                    return bid_price, ask_price
    else:
        print(f"Error fetching live price: {response.text}")
    return None, None

def get_historical_data(instrument, granularity="M15", count=500):
    url = f'{api_url}/instruments/{instrument}/candles'
    params = {
        'count': count,
        'price': 'MBA',
        'granularity': granularity
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        data = response.json()['candles']
        ohlc_data = []
        for candle in data:
            time = candle['time']
            open_price = float(candle['mid']['o'])
            high_price = float(candle['mid']['h'])
            low_price = float(candle['mid']['l'])
            close_price = float(candle['mid']['c'])
            ohlc_data.append([time, open_price, high_price, low_price, close_price])
        df = pd.DataFrame(ohlc_data, columns=['time', 'open', 'high', 'low', 'close'])
        df['time'] = pd.to_datetime(df['time'])
        return df
    else:
        print(f"Error fetching historical data: {response.text}")
        return None
def get_account_balance():
    url = f"{api_url}/accounts/{account_id}/summary"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        account_data = response.json()
        balance = float(account_data['account']['balance'])
        return balance
    else:
        print(f"Error fetching account balance: {response.text}")
        return None


def place_order(instrument, lot_size, entry_price, atr_value):
    pip_size = 0.0001 if instrument.endswith("USD") else 0.01
    stop_loss_price = entry_price - atr_value if lot_size > 0 else entry_price + atr_value

    order_data = {
        "order": {
            "units": str(lot_size),
            "instrument": instrument,
            "time_in_force": "GTC",
            "type": "MARKET",
            "position_fill": "DEFAULT",
            "stopLossOnFill": {"price": f"{stop_loss_price:.5f}"}
        }
    }

    url = f'{api_url}/accounts/{account_id}/orders'
    response = requests.post(url, headers=headers, data=json.dumps(order_data))
    if response.status_code == 201:
        # Extract relevant details from the response
        order_response = response.json()
        units = order_response['orderCreateTransaction']['units']

        entry_time = order_response['orderCreateTransaction']['time']
        stop_loss = order_response['orderCreateTransaction']['stopLossOnFill']['price']
        position_type = 'long' if int(units) > 0 else 'short'
        # Display extracted information
        print('Order Placed Succesfully......')
        print(order_response)
        print(f'Position Type: {position_type}')
        print(f'units: {units}')

        print(f'Entry Time: {entry_time}')
        print(f'Stop Loss Price: {stop_loss}')
        return True
    else:
        print(f"Error placing order: {response.text}")
        return False

def close_trade(instrument, units):
    url = f'{api_url}/accounts/{account_id}/orders'
    order_data = {
        "order": {
            "units": str(-units),
            "instrument": instrument,
            "time_in_force": "GTC",
            "type": "MARKET",
            "position_fill": "DEFAULT"
        }
    }
    response = requests.post(url, headers=headers, data=json.dumps(order_data))
    if response.status_code == 201:
        print(f"Trade closed successfully: {response.json()}")
    else:
        print(f"Error closing trade: {response.text}")

trade_open = False
current_position = 0

def get_open_positions():
    url = f'{api_url}/accounts/{account_id}/positions'
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        positions_data = response.json()
        for position in positions_data.get('positions', []):
            if position['instrument'] == 'EUR_USD':
                return position['long']['units'], position['short']['units']
    else:
        print(f"Error fetching open positions: {response.text}")
    return 0, 0
def supertrend_strategy():
    global trade_open, current_position
    instrument = 'EUR_USD'
    df = get_historical_data(instrument)

    if df is not None:

        df['ATR_14'] = ta.atr(high=df['high'], low=df['low'], close=df['close'], length=14)
        supertrend = df.ta.supertrend(high='high', low='low', close='close', length=12, multiplier=3.0)
        df['ST_direction'] = supertrend['SUPERTd_12_3.0']
        dema = ta.dema(df['close'], length=200)
        df['DEMA_200'] = round(dema, 5)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)  # Standard MACD settings
        df['MACD_Line'] = macd['MACD_12_26_9']  # MACD Line
        df['Signal_Line'] = macd['MACDs_12_26_9']  # Signal Line
        df['MACD_Histogram'] = macd['MACDh_12_26_9']  # Histogram
        df['MACD_Line'] = df['MACD_Line'].round(5)
        df['Signal_Line'] = df['Signal_Line'].round(5)
        df['MACD_Histogram'] = df['MACD_Histogram'].round(5)
        last_row = df.iloc[-1]
        previous_row = df.iloc[-2]
        atr_value = last_row['ATR_14'] * 2
        print(f"Previous row time is {previous_row['time']}")
        print(f"Previous row close :{previous_row['close']}")
        print(f"Previous row DEMA  :{previous_row['DEMA_200']}")
        print(f"Supertrend {previous_row['ST_direction']}")
        print("-----------------------------------------------")
        print(f"Last row time is {last_row['time']}")
        print(f"Last row close :{last_row['close']}")
        print(f"last row DEMA  :{last_row['DEMA_200']}")
        print(f"Supertrend {last_row['ST_direction']}")
        print(f"Last row MACD line        :{float(last_row['MACD_Line']):.6f}")
        print(f"Last row MACD SIgnal line :{float(last_row['Signal_Line']):.6f}")
        print("-----------------------------------------------")

        balance = get_account_balance()
        if balance is None:
            print("Failed to fetch account balance. Skipping strategy execution.")
            return
        risk_amount = (0.5/100)*balance
        lots = risk_amount/(atr_value*100000)
        size = lots
        lot_size = round(size * 100000)
        bid_price, ask_price = get_live_price(instrument)
        long_position, short_position = get_open_positions()
        if current_position == 0:
            if (last_row['ST_direction'] == 1
                and last_row['close'] > last_row['DEMA_200']
                and last_row['MACD_Line'] > last_row['Signal_Line']):
                if bid_price and ask_price:
                    trade_open = place_order(instrument, lot_size, ask_price, atr_value)
                    if trade_open:
                        current_position = 1

            elif last_row['ST_direction'] == -1 and last_row['close'] < last_row['DEMA_200'] and last_row['MACD_Line'] < last_row['Signal_Line']:
                print("Sell Signal: Supertrend is bearish")
                if bid_price and ask_price:
                    trade_open = place_order(instrument, -lot_size, bid_price, atr_value)
                    if trade_open:
                        current_position = -1

        elif current_position == 1 and last_row['ST_direction'] == -1:
            if int(long_position) > 0:
                print("Closing Buy Position: Supertrend turned bearish")
                close_trade(instrument, int(lot_size))
                current_position = 0

        elif current_position == -1 and last_row['ST_direction'] == 1:
            if int(short_position) > 0:
                print("Closing Sell Position: Supertrend turned bullish")
                close_trade(instrument, int(-lot_size))
                current_position = 0

def wait_until_next_interval():
    now = datetime.now(timezone.utc)
    next_interval = (now.minute // 15 + 1) * 15
    if next_interval == 60:
        next_interval = 0
        next_hour = (now.hour + 1) % 24
    else:
        next_hour = now.hour

    next_time = now.replace(hour=next_hour, minute=next_interval, second=0, microsecond=0)
    wait_time = (next_time - now).total_seconds()
    print(f"Waiting for {wait_time:.2f} seconds until the next interval.")
    time.sleep(wait_time)

while True:
    print("Executing Supertrend strategy...")
    print('================================')
    supertrend_strategy()
    wait_until_next_interval()
