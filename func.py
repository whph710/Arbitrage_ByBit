import requests


def get_bybit_linear_tickerst(symbol):
    """
        Получает список тикеров спотовых контрактов, от API Bybit.

        Возвращает:
            list: Список тикеров
        """
    url = "https://api.bybit.com/v5/market/tickers?category=spot"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Проверяем, успешный ли был запрос
        data = response.json()
        tickers_all = [pair["symbol"] for pair in data["result"]["list"]]
        tickers = [ticker for ticker in tickers_all if str(symbol) in ticker]

        return tickers
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return []


def get_trading_pairs():
    list_tickers = {}
    cross_pairs = ['USDT', 'EUR', 'BRL', 'PLN', 'TRY', 'SOL', 'BTC', 'ETH', 'DAI', 'BRZ']
    # Получение и обработка тикеров для каждой валюты
    for ticket in cross_pairs:
        tickers = get_bybit_linear_tickerst(ticket)
        new_tickers = []
        for pair in tickers:
            pair = pair.replace(ticket, '')
            new_tickers.append(pair)
        list_tickers[ticket] = new_tickers

    # Создание списка пар для каждой валюты
    trading_pairs = {}
    for base in cross_pairs:
        if base == 'USDT':
            continue
        trading_pairs[base] = []
        for quote in list_tickers[base]:
            if quote in list_tickers['USDT']:
                if base in ['USDT', 'BTC', 'ETH']:
                    trading_pairs[base].append((f"{quote}USDT", f"{quote}{base}", f"{base}USDT"))
                elif base in ['SOL']:
                    trading_pairs[base].append((f"{quote}USDT", f"{base}{quote}", f"{base}USDT"))
                else:
                    trading_pairs[base].append((f"{quote}USDT", f"{quote}{base}", f"USDT{base}"))

    return trading_pairs


def get_bybit_last_kline_data(symbol, category="spot", interval=1, limit=1):
    """
    Получает последние данные свечей (kline) для указанного символа и интервала от API Bybit.

    Параметры:
        symbol (str): Символ актива, для которого нужно получить данные свечей.
        interval (str): Интервал времени, для которого нужно получить данные свечей.
        limit (int, optional): Количество свечей, которое нужно получить. По умолчанию 50.

    Возвращает:
        list: Список данных свечей для указанного символа и интервала.
    """
    url = "https://api.bybit.com/v5/market/kline"

    params = {
        "category": category,
        "symbol": symbol,
        "interval": str(interval),
        "limit": limit
    }

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()  # Проверяем, успешный ли был запрос
        data = response.json()
        #print(data)
        return data["result"]["list"][0][4]
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return []


def calculate_profit(a=1, b=1, c=1, commission=0.0018):
    money = 100
    new_money = (((money / float(a)) * (1 - 0.002)) * float(b) * (1 - commission)) / float(c) * (1 - 0.002)
    percentage_change = ((new_money - money) / money) * 100
    return round(percentage_change, 3)



