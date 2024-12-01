import requests
import json
import time
import pandas as pd
from datetime import datetime, timezone

account_id = '101-001-29547380-001'
auth_key = 'cd7e3b0da2c80f1ea5aa8301910b7575-03e8dd1188a2d8f34ff8eec35c383401'
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


def get_historical_data(instrument, granularity="M15", count=200):
    url = f'{api_url}/instruments/{instrument}/candles'
    params = {
        'count': count,
        'price': 'M',
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


def calculate_moving_averages(df, short_period=10, long_period=11):
    df['SMA10'] = df['close'].rolling(window=short_period).mean()
    df['SMA11'] = df['close'].rolling(window=long_period).mean()
    return df


def place_order(instrument, units, entry_price, tp_pips, sl_pips):
    pip_size = 0.0001 if instrument.endswith("USD") else 0.01
    take_profit_price = entry_price + tp_pips * pip_size if units > 0 else entry_price - tp_pips * pip_size
    stop_loss_price = entry_price - sl_pips * pip_size if units > 0 else entry_price + sl_pips * pip_size

    order_data = {
        "order": {
            "units": str(units),
            "instrument": instrument,
            "time_in_force": "GTC",
            "type": "MARKET",
            "position_fill": "DEFAULT",
            "takeProfitOnFill": {"price": f"{take_profit_price:.5f}"},
            "stopLossOnFill": {"price": f"{stop_loss_price:.5f}"}
        }
    }

    url = f'{api_url}/accounts/{account_id}/orders'
    response = requests.post(url, headers=headers, data=json.dumps(order_data))
    if response.status_code == 201:
        print(f"Order placed successfully: {response.json()}")
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
        global trade_open
        trade_open = False
    else:
        print(f"Error closing trade: {response.text}")


def ma_crossover_strategy():
    current_position = 0
    instrument = 'EUR_USD'
    units = 100000
    df = get_historical_data(instrument)
    takeprofit = 1000
    stoploss = 5
    position_type = []

    if df is not None:
        df = calculate_moving_averages(df)
        last_row = df.iloc[-1]
        previous_row = df.iloc[-2]
        print(f"Previous SMA10:{previous_row['SMA10']:.5f}, SMA11: {previous_row['SMA11']:.5f},Time:{previous_row['time']}")
        print(f"Latest  SMA10:{last_row['SMA10']:.5f},      SMA11: {last_row['SMA11']:.5f},    Time:{last_row['time']}")

        if current_position == 0:

            if last_row['SMA10'] > last_row['SMA11']:
                print("Buy Signal: Fast MA crossed above Slow MA")
                bid_price, ask_price = get_live_price(instrument)
                if bid_price and ask_price:
                    trade_open = place_order(instrument, units, ask_price, takeprofit, stoploss)
                    entry_price = ask_price
                    position_type = "buy"
                    current_position = 1

            elif last_row['SMA10'] < last_row['SMA11']:
                print("Sell Signal: Fast MA crossed below Slow MA")
                bid_price, ask_price = get_live_price(instrument)
                if bid_price and ask_price:
                    trade_open = place_order(instrument, -units, bid_price, takeprofit, stoploss)
                    entry_price = bid_price
                    position_type = "sell"
                    current_position = -1

        elif current_position == 1:
            pip_size = 0.0001 if instrument.endswith("USD") else 0.01
            bid_price, ask_price = get_live_price(instrument)
            if last_row['SMA10'] < last_row['SMA11']:
                close_trade(instrument, units)
                print("Buy Signal: Fast MA crossed below Slow MA")
                current_position = 0

        elif current_position == -1:
            pip_size = 0.0001 if instrument.endswith("USD") else 0.01
            bid_price, ask_price = get_live_price(instrument)
            if last_row['SMA10'] > last_row['SMA11'] :
                close_trade(instrument, units)
                print("Sell Signal: Fast MA crossed above Slow MA")



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
    print("Executing strategy...")
    ma_crossover_strategy()
    wait_until_next_interval()
