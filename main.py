# main.py
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
    print("🚀 CRYPTO ARBITRAGE BOT")
    print("   Bybit ↔ BestChange")
    print("=" * 80)
    print(f"⏰ Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💰 Начальная сумма: ${Config.MIN_AMOUNT_USD}")
    print(f"📊 Минимальный спред: {Config.MIN_PROFIT_PERCENT}%")
    print(f"🎯 Показывать топ: {Config.TOP_OPPORTUNITIES} связок")
    print(f"⚠️  Расчёт БЕЗ учёта комиссий - компенсация спредом")
    print("=" * 80 + "\n")


def print_opportunities(opportunities: list):
    """Выводит найденные возможности в консоль"""
    if not opportunities:
        print("\n" + "=" * 80)
        print("❌ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НЕ НАЙДЕНО")
        print("=" * 80)
        print("\n💡 Возможные причины:")
        print("   • Рынок эффективен, большого спреда нет")
        print("   • Попробуйте снизить MIN_PROFIT_PERCENT в .env")
        print("   • Увеличьте MIN_AMOUNT_USD для лучших курсов")
        print("   • Запустите позже - курсы постоянно меняются")
        return

    print("\n" + "=" * 80)
    print(f"🏆 ТОП-{len(opportunities)} ПРИБЫЛЬНЫХ СВЯЗОК")
    print("=" * 80)

    for i, opp in enumerate(opportunities, 1):
        print(f"\n#{i}. {opp['crypto1']} → {opp['crypto2']}")
        print(f"   💵 Потенциальная прибыль: ${opp['potential_profit']} ({opp['spread_percent']}% спред)")
        print(f"   🏦 Обменник: {opp['step2_exchange']['exchanger_name']}")
        print(f"   📈 Курс BestChange: 1 {opp['crypto1']} = {opp['step2_exchange']['rate']:.8f} {opp['crypto2']}")
        print(
            f"   📊 Курс Bybit: 1 {opp['crypto1']} = {opp['rates_comparison'][f'{opp['crypto1']}_to_{opp['crypto2']}_bybit']:.8f} {opp['crypto2']}")
        print(f"   💎 Резерв: {opp['step2_exchange']['reserve']:.2f} {opp['crypto2']}")

        rate_diff = opp['rates_comparison']['rate_difference_percent']
        print(f"   {'✅' if rate_diff > 0 else '❌'} Разница курсов: {rate_diff:+.2f}%")

    print("\n" + "=" * 80)


def print_best_opportunity_details(best: dict):
    """Выводит детальную информацию о лучшей возможности"""
    print("\n" + "=" * 80)
    print("📊 ДЕТАЛИ ЛУЧШЕЙ ВОЗМОЖНОСТИ")
    print("=" * 80)

    print(f"\n🔄 Маршрут:")
    print(f"   {best['path']}")

    print(f"\n💰 Финансовые показатели (БЕЗ комиссий):")
    print(f"   Начальная сумма:      ${best['start_usdt']:,.2f}")
    print(f"   Конечная сумма:       ${best['final_usdt']:,.2f}")
    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Потенциальная прибыль: ${best['potential_profit']:,.2f} ({best['spread_percent']}%)")

    step1 = best['step1_buy']
    print(f"\n📈 ШАГ 1: Покупка на Bybit")
    print(f"   Покупаем:  {step1['amount']:.8f} {step1['crypto']}")
    print(f"   За:        ${step1['total_usdt']:,.2f}")
    print(f"   Цена:      ${step1['price_usdt']:.8f} за 1 {step1['crypto']}")

    step2 = best['step2_exchange']
    print(f"\n🔄 ШАГ 2: Обмен на {step2['exchanger_name']}")
    print(f"   Отдаём:    {step2['from_amount']:.8f} {step2['from_crypto']}")
    print(f"   Получаем:  {step2['to_amount']:.8f} {step2['to_crypto']}")
    print(f"   Курс:      1 {step2['from_crypto']} = {step2['rate']:.8f} {step2['to_crypto']}")
    print(f"   Резерв:    {step2['reserve']:,.2f} {step2['to_crypto']}")
    print(f"   Минимум:   {step2['min_amount']:.8f} {step2['from_crypto']}")

    step3 = best['step3_sell']
    print(f"\n📉 ШАГ 3: Продажа на Bybit")
    print(f"   Продаём:   {step3['amount']:.8f} {step3['crypto']}")
    print(f"   По цене:   ${step3['price_usdt']:.8f} за 1 {step3['crypto']}")
    print(f"   Получим:   ${step3['total_usdt']:,.2f}")

    rates = best['rates_comparison']
    print(f"\n📊 СРАВНЕНИЕ КУРСОВ:")
    print(
        f"   BestChange: 1 {best['crypto1']} = {rates[f'{best['crypto1']}_to_{best['crypto2']}_bestchange']:.8f} {best['crypto2']}")
    print(
        f"   Bybit:      1 {best['crypto1']} = {rates[f'{best['crypto1']}_to_{best['crypto2']}_bybit']:.8f} {best['crypto2']}")
    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Разница:    {rates['rate_difference_percent']:+.2f}%")

    print(f"\n⚠️  ВАЖНЫЕ ПРЕДУПРЕЖДЕНИЯ:")
    for warning in best['warnings']:
        print(f"   {warning}")

    print("\n💡 РЕКОМЕНДАЦИИ:")
    print("   • Комиссии биржи обычно 0.1-0.2% за сделку")
    print("   • Комиссия вывода зависит от сети (TRC20, BEP20, ERC20)")
    print("   • Учтите время подтверждения транзакций")
    print("   • Проверьте актуальные лимиты обменника")
    print("   • Цены могут измениться во время операции")

    print("\n" + "=" * 80)


def save_results(opportunities: list) -> str:
    """Сохраняет результаты в JSON файл"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = Config.RESULTS_DIR / f"arbitrage_{timestamp}.json"

    result_data = {
        'scan_info': {
            'timestamp': datetime.now().isoformat(),
            'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_opportunities_found': len(opportunities),
            'calculation_method': 'without_fees_compensation_by_spread'
        },
        'config': {
            'min_profit_percent': Config.MIN_PROFIT_PERCENT,
            'min_amount_usd': Config.MIN_AMOUNT_USD,
            'top_opportunities': Config.TOP_OPPORTUNITIES,
            'note': 'Calculations without fees - compensated by larger spread'
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
    print("📦 Инициализация компонентов...")
    bestchange = BestChangeHandler()
    bybit = BybitHandler()
    analyzer = ArbitrageAnalyzer(bestchange, bybit)

    # ═══════════════════════════════════════════════════════════════════════
    # ШАГ 1: ЗАГРУЖАЕМ ДАННЫЕ ИЗ BYBIT
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("📊 ШАГ 1: ЗАГРУЗКА ДАННЫХ ИЗ BYBIT")
    print("=" * 80)

    bybit_prices = bybit.get_all_tickers()

    if not bybit_prices:
        print("\n" + "=" * 80)
        print("✗ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 80)
        print("Не удалось загрузить данные с Bybit")
        print("\n💡 Что проверить:")
        print("   1. Подключение к интернету")
        print("   2. Доступность api.bybit.com")
        print("   3. Не заблокирован ли API в вашем регионе")
        print("\n" + "=" * 80)
        return

    bybit_tickers = set(bybit_prices.keys())
    print(f"\n✓ Загружено {len(bybit_tickers)} торговых пар USDT с Bybit")
    print(f"✓ Примеры тикеров: {', '.join(sorted(list(bybit_tickers))[:15])}")

    # ═══════════════════════════════════════════════════════════════════════
    # ШАГ 2: ЗАГРУЖАЕМ ДАННЫЕ ИЗ BESTCHANGE
    # ═══════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 80)
    print("📊 ШАГ 2: ЗАГРУЗКА ДАННЫХ ИЗ BESTCHANGE")
    print("=" * 80)

    if not bestchange.update_data(bybit_tickers):
        print("\n" + "=" * 80)
        print("✗ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 80)
        print("Не удалось загрузить данные с BestChange")
        print("\n💡 Что проверить:")
        print("   1. API ключ BestChange в .env файле")
        print("   2. Подключение к интернету")
        print("   3. Доступность bestchange.app")
        print("\n" + "=" * 80)
        return

    # ═══════════════════════════════════════════════════════════════════════
    # ШАГ 3: АНАЛИЗ И ПОИСК ВОЗМОЖНОСТЕЙ
    # ═══════════════════════════════════════════════════════════════════════
    opportunities = analyzer.find_opportunities()

    # Вывод результатов в консоль
    print_opportunities(opportunities)

    # Сохранение результатов
    if opportunities:
        print("\n💾 Сохранение результатов...")
        filename = save_results(opportunities)
        print(f"✓ Результаты сохранены: {filename}")

        # Выводим детали лучшей возможности
        print_best_opportunity_details(opportunities[0])
    else:
        print("\n💡 Рекомендации:")
        print("   • Попробуйте снизить MIN_PROFIT_PERCENT в .env файле")
        print("   • Запустите бота позже, когда появятся арбитражные возможности")
        print("   • Увеличьте MIN_AMOUNT_USD для работы с большими суммами")

    # Финальное сообщение
    print("\n✅ АНАЛИЗ ЗАВЕРШЁН")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Программа прервана пользователем")
        print("=" * 80 + "\n")
    except Exception as e:
        print(f"\n\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("=" * 80)
        import traceback

        traceback.print_exc()
        print("=" * 80 + "\n")