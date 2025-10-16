import json
from datetime import datetime
from pathlib import Path
from configs import Config
from bestchange_handler import BestChangeHandler
from bybit_handler import BybitHandler
from arbitrage_analyzer import ArbitrageAnalyzer


def print_header():
    """Выводит заголовок программы"""
    print("\n" + "=" * 80)
    print("🚀 ARBITRAGE BOT - Bybit ↔ BestChange")
    print("=" * 80)
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Минимальная прибыль: {Config.MIN_PROFIT_PERCENT}%")
    print(f"Начальная сумма: ${Config.MIN_AMOUNT_USD}")
    print(f"Топ связок для сохранения: {Config.TOP_OPPORTUNITIES}")
    print("=" * 80 + "\n")


def print_opportunities(opportunities: list):
    """Выводит найденные возможности в консоль"""
    if not opportunities:
        print("\n❌ Арбитражных возможностей не найдено")
        return

    print("\n" + "=" * 80)
    print(f"🏆 ТОП-{len(opportunities)} АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ")
    print("=" * 80)

    for i, opp in enumerate(opportunities, 1):
        print(f"\n#{i}. {opp['crypto1']} → {opp['crypto2']}")
        print(f"   Прибыль: {opp['profit_percent']}% (${opp['net_profit']})")
        print(f"   Обменник: {opp['step2_exchange']['exchanger_name']}")
        print(f"   Курс: 1 {opp['crypto1']} = {opp['step2_exchange']['rate']} {opp['crypto2']}")
        print(f"   Резерв: {opp['step2_exchange']['reserve']} {opp['crypto2']}")

    print("\n" + "=" * 80)


def save_results(opportunities: list) -> str:
    """Сохраняет результаты в JSON файл"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = Config.RESULTS_DIR / f"arbitrage_{timestamp}.json"

    result_data = {
        'scan_info': {
            'timestamp': datetime.now().isoformat(),
            'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_opportunities_found': len(opportunities)
        },
        'config': {
            'min_profit_percent': Config.MIN_PROFIT_PERCENT,
            'min_amount_usd': Config.MIN_AMOUNT_USD,
            'top_opportunities': Config.TOP_OPPORTUNITIES,
            'bybit_trading_fee': Config.BYBIT_TRADING_FEE,
            'withdrawal_fee_usd': Config.WITHDRAWAL_FEE_USD,
            'deposit_fee_usd': Config.DEPOSIT_FEE_USD
        },
        'opportunities': opportunities
    }

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, indent=2, ensure_ascii=False)

    return str(filename)


def main():
    """Основная функция программы"""

    # Выводим заголовок
    print_header()

    # Инициализация обработчиков
    print("📦 Инициализация...")
    bestchange = BestChangeHandler()
    bybit = BybitHandler()
    analyzer = ArbitrageAnalyzer(bestchange, bybit)

    # Загрузка данных BestChange
    print("\n📥 Загрузка данных...")
    if not bestchange.update_data():
        print("\n✗ ОШИБКА: Не удалось загрузить данные BestChange")
        print("Проверьте подключение к интернету и повторите попытку")
        return

    # Поиск возможностей
    opportunities = analyzer.find_opportunities()

    # Вывод результатов в консоль
    print_opportunities(opportunities)

    # Сохранение результатов
    if opportunities:
        print("\n💾 Сохранение результатов...")
        filename = save_results(opportunities)
        print(f"✓ Результаты сохранены: {filename}")

        # Выводим детали лучшей возможности
        best = opportunities[0]
        print("\n" + "=" * 80)
        print("📊 ДЕТАЛИ ЛУЧШЕЙ ВОЗМОЖНОСТИ:")
        print("=" * 80)
        print(f"\n🔄 Путь: {best['path']}")
        print(f"\n💰 Финансы:")
        print(f"   Начальная сумма:  ${best['start_usdt']}")
        print(f"   Конечная сумма:   ${best['final_usdt']}")
        print(f"   Чистая прибыль:   ${best['net_profit']}")
        print(f"   Процент прибыли:  {best['profit_percent']}%")
        print(f"   Комиссии (всего): ${best['total_fees']}")

        print(f"\n📈 Шаги выполнения:")
        step1 = best['step1_buy_crypto1']
        print(f"   1. Купить на Bybit:")
        print(f"      {step1['amount']} {step1['crypto']} за ${step1['total_usdt']}")
        print(f"      Цена: ${step1['price_usdt']} за 1 {step1['crypto']}")

        step2 = best['step2_exchange']
        print(f"\n   2. Обменять на {step2['exchanger_name']}:")
        print(f"      {step2['from_amount']} {step2['from_crypto']} → {step2['to_amount']} {step2['to_crypto']}")
        print(f"      Курс: 1 {step2['from_crypto']} = {step2['rate']} {step2['to_crypto']}")
        print(f"      Резерв: {step2['reserve']} {step2['to_crypto']}")

        step3 = best['step3_sell_crypto2']
        print(f"\n   3. Продать на Bybit:")
        print(f"      {step3['amount']} {step3['crypto']} за ${step3['total_usdt']}")
        print(f"      Цена: ${step3['price_usdt']} за 1 {step3['crypto']}")

        print("\n" + "=" * 80)

    # Финальное сообщение
    print("\n✅ АНАЛИЗ ЗАВЕРШЁН")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Программа прервана пользователем")
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()