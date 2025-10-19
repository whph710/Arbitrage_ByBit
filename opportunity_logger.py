"""
Модуль для логирования найденных арбитражных возможностей
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from configs_continuous import LOGS_DIR, SAVE_OPPORTUNITIES_TO_FILE


class OpportunityLogger:
    """Логгер для записи найденных арбитражных возможностей"""

    def __init__(self):
        self.logs_dir = LOGS_DIR
        self.logs_dir.mkdir(exist_ok=True)

        # Файлы логов
        self.opportunities_log = self.logs_dir / "opportunities.log"
        self.daily_summary_log = self.logs_dir / "daily_summary.log"

        # Статистика за текущую сессию
        self.session_opportunities = []
        self.session_start = datetime.now()

        # Счетчики
        self.total_logged = 0
        self.best_spread = 0
        self.best_opportunity = None

    def log_opportunity(self, opportunity: Dict):
        """
        Логирует найденную возможность в файл и память

        Args:
            opportunity: Словарь с данными возможности
        """
        if not SAVE_OPPORTUNITIES_TO_FILE:
            return

        try:
            timestamp = datetime.now()

            # Добавляем временную метку
            log_entry = {
                'timestamp': timestamp.isoformat(),
                'opportunity': opportunity
            }

            # Записываем в файл
            with open(self.opportunities_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')

            # Сохраняем в памяти для статистики
            self.session_opportunities.append(log_entry)
            self.total_logged += 1

            # Обновляем лучшую находку
            if opportunity['spread'] > self.best_spread:
                self.best_spread = opportunity['spread']
                self.best_opportunity = opportunity

        except Exception as e:
            print(f"⚠️  Ошибка при логировании: {e}")

    def log_text(self, message: str):
        """Логирует текстовое сообщение"""
        if not SAVE_OPPORTUNITIES_TO_FILE:
            return

        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            with open(self.opportunities_log, 'a', encoding='utf-8') as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"⚠️  Ошибка при логировании текста: {e}")

    def get_session_statistics(self) -> Dict:
        """Возвращает статистику текущей сессии"""
        uptime = datetime.now() - self.session_start

        stats = {
            'session_start': self.session_start.isoformat(),
            'uptime_seconds': uptime.total_seconds(),
            'uptime_hours': uptime.total_seconds() / 3600,
            'total_opportunities': self.total_logged,
            'best_spread': self.best_spread,
            'best_opportunity': self.best_opportunity
        }

        # Статистика по обменникам
        if self.session_opportunities:
            exchangers = {}
            for entry in self.session_opportunities:
                opp = entry['opportunity']
                ex = opp.get('exchanger', 'Unknown')
                if ex not in exchangers:
                    exchangers[ex] = {'count': 0, 'total_profit': 0, 'max_spread': 0}
                exchangers[ex]['count'] += 1
                exchangers[ex]['total_profit'] += opp['profit']
                exchangers[ex]['max_spread'] = max(exchangers[ex]['max_spread'], opp['spread'])

            stats['top_exchangers'] = sorted(
                exchangers.items(),
                key=lambda x: x[1]['count'],
                reverse=True
            )[:5]

        # Статистика по монетам
        if self.session_opportunities:
            coins = {}
            for entry in self.session_opportunities:
                opp = entry['opportunity']
                for coin in opp.get('coins', []):
                    if coin not in coins:
                        coins[coin] = 0
                    coins[coin] += 1

            stats['top_coins'] = sorted(
                coins.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]

        return stats

    def save_daily_summary(self):
        """Сохраняет дневную статистику"""
        try:
            stats = self.get_session_statistics()

            summary = {
                'date': datetime.now().strftime('%Y-%m-%d'),
                'statistics': stats
            }

            with open(self.daily_summary_log, 'a', encoding='utf-8') as f:
                f.write(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
                f.write('-' * 100 + '\n')

            print(f"\n📊 Дневная статистика сохранена в {self.daily_summary_log}")

        except Exception as e:
            print(f"⚠️  Ошибка при сохранении дневной статистики: {e}")

    def print_session_summary(self):
        """Выводит сводку по текущей сессии"""
        stats = self.get_session_statistics()

        print(f"\n{'='*100}")
        print(f"📊 СТАТИСТИКА СЕССИИ")
        print(f"{'='*100}")
        print(f"⏱️  Время работы: {stats['uptime_hours']:.1f} часов")
        print(f"🎯 Связок найдено: {stats['total_opportunities']}")

        if stats['total_opportunities'] > 0:
            print(f"🏆 Лучший спред: {stats['best_spread']:.4f}%")

            if stats['best_opportunity']:
                print(f"   Путь: {stats['best_opportunity']['path']}")
                print(f"   Прибыль: ${stats['best_opportunity']['profit']:.4f}")
                print(f"   Обменник: {stats['best_opportunity']['exchanger']}")

        if 'top_exchangers' in stats and stats['top_exchangers']:
            print(f"\n🏦 ТОП-5 ОБМЕННИКОВ:")
            for ex, ex_stats in stats['top_exchangers']:
                print(f"   {ex}: {ex_stats['count']} связок, макс. спред {ex_stats['max_spread']:.4f}%")

        if 'top_coins' in stats and stats['top_coins']:
            print(f"\n💰 ТОП-10 МОНЕТ:")
            for coin, count in stats['top_coins']:
                print(f"   {coin}: {count} появлений")

        print(f"{'='*100}\n")

    def load_recent_opportunities(self, hours: int = 24) -> List[Dict]:
        """
        Загружает недавние возможности из лога

        Args:
            hours: Количество часов для загрузки

        Returns:
            Список возможностей
        """
        if not self.opportunities_log.exists():
            return []

        opportunities = []
        cutoff_time = datetime.now().timestamp() - (hours * 3600)

        try:
            with open(self.opportunities_log, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        entry = json.loads(line.strip())
                        entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()

                        if entry_time >= cutoff_time:
                            opportunities.append(entry)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

            return opportunities

        except Exception as e:
            print(f"⚠️  Ошибка при загрузке логов: {e}")
            return []

    def analyze_recent_trends(self, hours: int = 24):
        """Анализирует тренды за последние N часов"""
        opportunities = self.load_recent_opportunities(hours)

        if not opportunities:
            print(f"\n⚠️  Нет данных за последние {hours} часов")
            return

        print(f"\n{'='*100}")
        print(f"📈 АНАЛИЗ ТРЕНДОВ ЗА ПОСЛЕДНИЕ {hours} ЧАСОВ")
        print(f"{'='*100}")
        print(f"📊 Всего записей: {len(opportunities)}")

        # Средний спред
        spreads = [opp['opportunity']['spread'] for opp in opportunities]
        avg_spread = sum(spreads) / len(spreads) if spreads else 0
        max_spread = max(spreads) if spreads else 0

        print(f"💰 Средний спред: {avg_spread:.4f}%")
        print(f"🏆 Максимальный спред: {max_spread:.4f}%")

        # Топ обменники
        exchangers = {}
        for entry in opportunities:
            ex = entry['opportunity'].get('exchanger', 'Unknown')
            exchangers[ex] = exchangers.get(ex, 0) + 1

        print(f"\n🏦 САМЫЕ АКТИВНЫЕ ОБМЕННИКИ:")
        for ex, count in sorted(exchangers.items(), key=lambda x: x[1], reverse=True)[:5]:
            percentage = (count / len(opportunities)) * 100
            print(f"   {ex}: {count} связок ({percentage:.1f}%)")

        # Топ монеты
        coins = {}
        for entry in opportunities:
            for coin in entry['opportunity'].get('coins', []):
                coins[coin] = coins.get(coin, 0) + 1

        print(f"\n💎 САМЫЕ ПОПУЛЯРНЫЕ МОНЕТЫ:")
        for coin, count in sorted(coins.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {coin}: {count} появлений")

        # Временное распределение (по часам)
        hourly_distribution = {}
        for entry in opportunities:
            hour = datetime.fromisoformat(entry['timestamp']).hour
            hourly_distribution[hour] = hourly_distribution.get(hour, 0) + 1

        print(f"\n⏰ РАСПРЕДЕЛЕНИЕ ПО ЧАСАМ:")
        for hour in sorted(hourly_distribution.keys()):
            count = hourly_distribution[hour]
            bar = '█' * (count // 2)
            print(f"   {hour:02d}:00 - {count:3d} | {bar}")

        print(f"{'='*100}\n")

    def export_to_csv(self, output_file: Path = None, hours: int = 24):
        """Экспортирует данные в CSV"""
        if output_file is None:
            output_file = self.logs_dir / f"opportunities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        opportunities = self.load_recent_opportunities(hours)

        if not opportunities:
            print(f"⚠️  Нет данных для экспорта")
            return

        try:
            import csv

            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)

                # Заголовки
                writer.writerow([
                    'Timestamp',
                    'Path',
                    'Spread %',
                    'Profit $',
                    'Initial $',
                    'Final $',
                    'Exchanger',
                    'Reserve $',
                    'Coins',
                    'Liquidity A',
                    'Liquidity B'
                ])

                # Данные
                for entry in opportunities:
                    opp = entry['opportunity']
                    writer.writerow([
                        entry['timestamp'],
                        opp['path'],
                        f"{opp['spread']:.4f}",
                        f"{opp['profit']:.4f}",
                        f"{opp['initial']:.2f}",
                        f"{opp['final']:.2f}",
                        opp.get('exchanger', 'N/A'),
                        f"{opp.get('reserve', 0):.0f}",
                        ' → '.join(opp.get('coins', [])),
                        f"{opp.get('liquidity_a', 0):.1f}",
                        f"{opp.get('liquidity_b', 0):.1f}"
                    ])

            print(f"\n✅ Данные экспортированы в {output_file}")

        except Exception as e:
            print(f"❌ Ошибка при экспорте в CSV: {e}")