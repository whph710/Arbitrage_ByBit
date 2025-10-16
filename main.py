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
    print(f"📊 Минимальная прибыль: {Config.MIN_PROFIT_PERCENT}%")
    print(f"🎯 Показывать топ: {Config.TOP_OPPORTUNITIES} связок")
    print("=" * 80 + "\n")


def print_opportunities(opportunities: list):
    """Выводит найденные возможности в консоль"""
    if not opportunities:
        print("\n" + "=" * 80)
        print("❌ АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НЕ НАЙДЕНО")
        print("=" * 80)
        print("\n💡 Возможные причины:")
        print("   • Рынок эффективен, арбитраж отсутствует")
        print("   • Комиссии превышают разницу в ценах")
        print("   • Попробуйте снизить MIN_PROFIT_PERCENT в .env")
        print("   • Увеличьте MIN_AMOUNT_USD для лучших курсов")
        return

    print("\n" + "=" * 80)
    print(f"🏆 ТОП-{len(opportunities)} ПРИБЫЛЬНЫХ СВЯЗОК")
    print("=" * 80)

    for i, opp in enumerate(opportunities, 1):
        print(f"\n#{i}. {opp['crypto1']} → {opp['crypto2']}")
        print(f"   💵 Прибыль: ${opp['net_profit']} ({opp['profit_percent']}%)")
        print(f"   🏦 Обменник: {opp['step2_exchange']['exchanger_name']}")
        print(f"   📈 Курс: 1 {opp['crypto1']} = {opp['step2_exchange']['rate']:.8f} {opp['crypto2']}")
        print(f"   💎 Резерв: {opp['step2_exchange']['reserve']:.2f} {opp['crypto2']}")

        if opp.get('is_better_than_direct'):
            print(f"   ✅ Выгоднее прямого обмена на ${opp['advantage_over_direct']:.2f}")
        else:
            print(f"   ⚠️  Прямой обмен на Bybit выгоднее на ${abs(opp['advantage_over_direct']):.2f}")

    print("\n" + "=" * 80)


def print_best_opportunity_details(best: dict):
    """Выводит детальную информацию о лучшей возможности"""
    print("\n" + "=" * 80)
    print("📊 ДЕТАЛИ ЛУЧШЕЙ ВОЗМОЖНОСТИ")
    print("=" * 80)

    print(f"\n🔄 Маршрут:")
    print(f"   {best['path']}")

    print(f"\n💰 Финансовые показатели:")
    print(f"   Начальная сумма:  ${best['start_usdt']:,.2f}")
    print(f"   Конечная сумма:   ${best['final_usdt']:,.2f}")
    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Чистая прибыль:   ${best['net_profit']:,.2f} ({best['profit_percent']}%)")
    print(f"   Комиссии (всего): ${best['total_fees']:,.2f}")

    step1 = best['step1_buy_crypto1']
    print(f"\n📈 ШАГ 1: Покупка на Bybit")
    print(f"   Покупаем:  {step1['amount_before_withdrawal']:.8f} {step1['crypto']}")
    print(f"   За:        ${step1['total_usdt']:,.2f}")
    print(f"   Цена:      ${step1['price_usdt']:.8f} за 1 {step1['crypto']}")
    print(f"   Комиссия:  ${step1['trading_fee']:.2f}")
    print(f"   Вывод:     ${step1['withdrawal_fee_usd']:.2f} ({step1['withdrawal_fee_crypto']:.8f} {step1['crypto']})")
    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Получим:   {step1['amount_after_withdrawal']:.8f} {step1['crypto']}")

    step2 = best['step2_exchange']
    print(f"\n🔄 ШАГ 2: Обмен на {step2['exchanger_name']}")
    print(f"   Отдаём:    {step2['from_amount']:.8f} {step2['from_crypto']}")
    print(f"   Получаем:  {step2['to_amount']:.8f} {step2['to_crypto']}")
    print(f"   Курс:      1 {step2['from_crypto']} = {step2['rate']:.8f} {step2['to_crypto']}")
    print(f"   Резерв:    {step2['reserve']:,.2f} {step2['to_crypto']}")

    step3 = best['step3_sell_crypto2']
    print(f"\n📉 ШАГ 3: Продажа на Bybit")
    print(f"   Депозит:   {step3['amount_before_deposit']:.8f} {step3['crypto']}")
    print(f"   Комиссия:  ${step3['deposit_fee_usd']:.2f} ({step3['deposit_fee_crypto']:.8f} {step3['crypto']})")
    print(f"   Продаём:   {step3['amount_after_deposit']:.8f} {step3['crypto']}")
    print(f"   По цене:   ${step3['price_usdt']:.8f} за 1 {step3['crypto']}")
    print(f"   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"   Получим:   ${step3['total_usdt']:,.2f}")

    print(f"\n⚠️  ВАЖНЫЕ ПРЕДУПРЕЖДЕНИЯ:")
    for warning in best['warnings']:
        print(f"   {warning}")

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
            'profitable_opportunities': len([o for o in opportunities if o['profit_percent'] > 0])
        },
        'config': {
            'min_profit_percent': Config.MIN_PROFIT_PERCENT,
            'min_amount_usd': Config.MIN_AMOUNT_USD,
            'top_opportunities': Config.TOP_OPPORTUNITIES,
            'fees': {
                'bybit_trading_fee': Config.BYBIT_TRADING_FEE,
                'withdrawal_fee_usd': Config.WITHDRAWAL_FEE_USD,
                'deposit_fee_usd': Config.DEPOSIT_FEE_USD
            }
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

    # Загрузка данных BestChange
    print("\n📥 Загрузка данных с BestChange...")
    if not bestchange.update_data():
        print("\n" + "=" * 80)
        print("✗ КРИТИЧЕСКАЯ ОШИБКА")
        print("=" * 80)
        print("Не удалось загрузить данные с BestChange")
        print("\n💡 Что проверить:")
        print("   1. Подключение к интернету")
        print("   2. Доступность api.bestchange.ru")
        print("   3. Корректность URL в configs.py")
        print("\n" + "=" * 80)
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
