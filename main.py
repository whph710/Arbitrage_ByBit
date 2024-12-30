from func import get_trading_pairs, get_bybit_last_kline_data, calculate_profit


try:

    while True:
        for base, list_pairs in get_trading_pairs().items():
            for pair in list_pairs:
                print(pair)
                num_list = []
                for trade_pair in pair:
                    if base in ['USDT', 'SOL', 'BTC', 'ETH']:
                        try:
                            ab = get_bybit_last_kline_data(trade_pair)
                        except Exception as e:
                            print(e)
                            continue
                    else:
                        ab = get_bybit_last_kline_data(trade_pair)
                    num_list.append(ab)
                try:
                    a, b, c = num_list
                    num_list.append(calculate_profit(a, b, c))
                except Exception as e:
                    print(e)
                    continue
                print(num_list)


except Exception as e:
    print(e)

