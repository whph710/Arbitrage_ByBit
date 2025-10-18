import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from configs import RESULTS_DIR


class ResultsSaver:
    """Класс для сохранения результатов арбитража в различных форматах"""

    def __init__(self, results_dir: Path = RESULTS_DIR):
        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)

    def save_opportunities(
            self,
            opportunities: List[Dict],
            start_amount: float,
            min_spread: float,
            execution_time: float,
            save_formats: List[str] = ['json', 'txt', 'csv']
    ) -> Dict[str, Path]:
        """
        Сохраняет результаты в указанных форматах

        Args:
            opportunities: список найденных арбитражных возможностей
            start_amount: начальная сумма
            min_spread: минимальный спред
            execution_time: время выполнения в секундах
            save_formats: форматы для сохранения ['json', 'txt', 'csv', 'html']

        Returns:
            словарь с путями к сохранённым файлам
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_files = {}

        # Метаданные
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'start_amount': start_amount,
            'min_spread': min_spread,
            'execution_time': execution_time,
            'total_opportunities': len(opportunities)
        }

        # Сохранение в JSON
        if 'json' in save_formats:
            json_path = self.results_dir / f'arbitrage_{timestamp}.json'
            self._save_json(json_path, opportunities, metadata)
            saved_files['json'] = json_path

        # Сохранение в TXT
        if 'txt' in save_formats:
            txt_path = self.results_dir / f'arbitrage_{timestamp}.txt'
            self._save_txt(txt_path, opportunities, metadata)
            saved_files['txt'] = txt_path

        # Сохранение в CSV
        if 'csv' in save_formats:
            csv_path = self.results_dir / f'arbitrage_{timestamp}.csv'
            self._save_csv(csv_path, opportunities, metadata)
            saved_files['csv'] = csv_path

        # Сохранение в HTML
        if 'html' in save_formats:
            html_path = self.results_dir / f'arbitrage_{timestamp}.html'
            self._save_html(html_path, opportunities, metadata)
            saved_files['html'] = html_path

        return saved_files

    def _save_json(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в JSON формате"""
        data = {
            'metadata': metadata,
            'opportunities': opportunities
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _save_txt(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в текстовом формате"""
        with open(path, 'w', encoding='utf-8') as f:
            # Заголовок
            f.write("=" * 100 + "\n")
            f.write("🚀 CRYPTO ARBITRAGE BOT — РЕЗУЛЬТАТЫ АНАЛИЗА\n")
            f.write("=" * 100 + "\n\n")

            # Метаданные
            f.write(f"📅 Дата и время: {metadata['timestamp']}\n")
            f.write(f"💰 Начальная сумма: ${metadata['start_amount']:.2f}\n")
            f.write(f"📊 Минимальный спред: {metadata['min_spread']}%\n")
            f.write(f"⏱️  Время выполнения: {metadata['execution_time']:.2f} сек\n")
            f.write(f"🎯 Найдено возможностей: {metadata['total_opportunities']}\n\n")

            # Статистика по схемам
            if opportunities:
                schemes_stats = self._calculate_schemes_stats(opportunities)
                f.write("=" * 100 + "\n")
                f.write("📈 СТАТИСТИКА ПО СХЕМАМ\n")
                f.write("=" * 100 + "\n\n")

                for scheme, stats in sorted(schemes_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                    f.write(f"• {scheme}\n")
                    f.write(f"  Найдено: {stats['count']} возможностей\n")
                    f.write(f"  Макс. спред: {stats['max_spread']:.4f}%\n")
                    f.write(f"  Общая потенциальная прибыль: ${stats['total_profit']:.2f}\n\n")

            # Детальный список возможностей
            if opportunities:
                f.write("\n" + "=" * 100 + "\n")
                f.write(f"🎯 ТОП-{len(opportunities)} АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ\n")
                f.write("=" * 100 + "\n\n")

                for idx, opp in enumerate(opportunities, 1):
                    f.write(f"#{idx} | Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}\n")
                    f.write(f"    Схема: {opp['scheme']}\n")
                    f.write(f"    Путь: {opp['path']}\n")
                    f.write(f"    Детали:\n")
                    for step in opp['steps']:
                        f.write(f"       {step}\n")

                    if 'debug' in opp and 'reserve' in opp['debug']:
                        reserve = opp['debug'].get('reserve', 0)
                        if reserve > 0:
                            f.write(f"    💰 Резерв обменника: ${reserve:.2f}\n")
                    f.write("\n")

            # Предупреждения
            f.write("\n" + "=" * 100 + "\n")
            f.write("⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ\n")
            f.write("=" * 100 + "\n\n")
            f.write("1. Указанные спреды НЕ учитывают комиссии бирж (обычно 0.1-0.2% за сделку)\n")
            f.write("2. Обменники BestChange берут комиссию (обычно 0.5-2%)\n")
            f.write("3. Переводы между биржами требуют времени и комиссий за вывод\n")
            f.write("4. Проскальзывание цены может съесть часть прибыли\n")
            f.write("5. Резервы обменников могут быть недостаточными для крупных сумм\n")
            f.write("6. Всегда проверяйте актуальность данных перед совершением сделок!\n")

    def _save_csv(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в CSV формате"""
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # Заголовки
            writer.writerow([
                'Rank',
                'Scheme',
                'Path',
                'Spread %',
                'Profit $',
                'Initial $',
                'Final $',
                'Buy Exchange',
                'Sell Exchange',
                'Coins',
                'Steps'
            ])

            # Данные
            for idx, opp in enumerate(opportunities, 1):
                buy_exchange = opp.get('debug', {}).get('buy_exchange', 'N/A')
                sell_exchange = opp.get('debug', {}).get('sell_exchange', 'N/A')
                coins = ' → '.join(opp.get('coins', []))
                steps = ' | '.join(opp.get('steps', []))

                writer.writerow([
                    idx,
                    opp['scheme'],
                    opp['path'],
                    f"{opp['spread']:.4f}",
                    f"{opp['profit']:.2f}",
                    f"{opp['initial']:.2f}",
                    f"{opp['final']:.2f}",
                    buy_exchange,
                    sell_exchange,
                    coins,
                    steps
                ])

    def _save_html(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в HTML формате с красивым оформлением"""
        html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Arbitrage Results - {metadata['timestamp']}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #f5f5f5; padding: 20px; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; }}
        .header h1 {{ margin-bottom: 10px; }}
        .metadata {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; padding: 20px; background: #f8f9fa; }}
        .metadata-item {{ padding: 15px; background: white; border-radius: 5px; border-left: 4px solid #667eea; }}
        .metadata-item strong {{ display: block; color: #667eea; margin-bottom: 5px; }}
        .stats {{ padding: 20px; }}
        .scheme-stat {{ padding: 15px; margin: 10px 0; background: #f8f9fa; border-radius: 5px; border-left: 4px solid #28a745; }}
        .opportunities {{ padding: 20px; }}
        .opportunity {{ margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 5px; border-left: 4px solid #667eea; }}
        .opportunity-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
        .opportunity-rank {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .spread {{ font-size: 20px; font-weight: bold; color: #28a745; }}
        .profit {{ font-size: 18px; color: #28a745; }}
        .scheme-badge {{ display: inline-block; padding: 5px 15px; background: #667eea; color: white; border-radius: 20px; font-size: 12px; }}
        .path {{ font-weight: bold; color: #333; margin: 10px 0; }}
        .steps {{ margin-top: 15px; padding-left: 20px; }}
        .step {{ padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
        .step:last-child {{ border-bottom: none; }}
        .reserve {{ margin-top: 10px; padding: 10px; background: #fff3cd; border-radius: 5px; color: #856404; }}
        .warning {{ background: #fff3cd; padding: 20px; margin: 20px; border-radius: 5px; border-left: 4px solid #ffc107; }}
        .warning h3 {{ color: #856404; margin-bottom: 10px; }}
        .warning ul {{ padding-left: 20px; }}
        .warning li {{ margin: 5px 0; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Crypto Arbitrage Bot — Результаты анализа</h1>
            <p>Мульти-биржевой поиск арбитражных возможностей</p>
        </div>

        <div class="metadata">
            <div class="metadata-item">
                <strong>📅 Дата и время</strong>
                {metadata['timestamp']}
            </div>
            <div class="metadata-item">
                <strong>💰 Начальная сумма</strong>
                ${metadata['start_amount']:.2f}
            </div>
            <div class="metadata-item">
                <strong>📊 Минимальный спред</strong>
                {metadata['min_spread']}%
            </div>
            <div class="metadata-item">
                <strong>⏱️ Время выполнения</strong>
                {metadata['execution_time']:.2f} сек
            </div>
            <div class="metadata-item">
                <strong>🎯 Найдено возможностей</strong>
                {metadata['total_opportunities']}
            </div>
        </div>
"""

        # Статистика по схемам
        if opportunities:
            schemes_stats = self._calculate_schemes_stats(opportunities)
            html_content += """
        <div class="stats">
            <h2>📈 Статистика по схемам</h2>
"""
            for scheme, stats in sorted(schemes_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                html_content += f"""
            <div class="scheme-stat">
                <strong>{scheme}</strong><br>
                Найдено: {stats['count']} возможностей | 
                Макс. спред: {stats['max_spread']:.4f}% | 
                Общая прибыль: ${stats['total_profit']:.2f}
            </div>
"""
            html_content += """
        </div>
"""

        # Список возможностей
        if opportunities:
            html_content += """
        <div class="opportunities">
            <h2>🎯 Топ арбитражных возможностей</h2>
"""
            for idx, opp in enumerate(opportunities, 1):
                reserve_html = ""
                if 'debug' in opp and 'reserve' in opp['debug']:
                    reserve = opp['debug'].get('reserve', 0)
                    if reserve > 0:
                        reserve_html = f'<div class="reserve">💰 Резерв обменника: ${reserve:.2f}</div>'

                steps_html = ""
                for step in opp['steps']:
                    steps_html += f'<div class="step">{step}</div>'

                html_content += f"""
            <div class="opportunity">
                <div class="opportunity-header">
                    <div>
                        <span class="opportunity-rank">#{idx}</span>
                        <span class="scheme-badge">{opp['scheme']}</span>
                    </div>
                    <div>
                        <span class="spread">{opp['spread']:.4f}%</span>
                        <span class="profit"> | Прибыль: ${opp['profit']:.4f}</span>
                    </div>
                </div>
                <div class="path">Путь: {opp['path']}</div>
                <div class="steps">
                    <strong>Детали:</strong>
                    {steps_html}
                </div>
                {reserve_html}
            </div>
"""
            html_content += """
        </div>
"""

        # Предупреждения
        html_content += """
        <div class="warning">
            <h3>⚠️ Важные замечания</h3>
            <ul>
                <li>Указанные спреды НЕ учитывают комиссии бирж (обычно 0.1-0.2% за сделку)</li>
                <li>Обменники BestChange берут комиссию (обычно 0.5-2%)</li>
                <li>Переводы между биржами требуют времени и комиссий за вывод</li>
                <li>Проскальзывание цены может съесть часть прибыли</li>
                <li>Резервы обменников могут быть недостаточными для крупных сумм</li>
                <li>Всегда проверяйте актуальность данных перед совершением сделок!</li>
            </ul>
        </div>
    </div>
</body>
</html>"""

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _calculate_schemes_stats(self, opportunities: List[Dict]) -> Dict:
        """Подсчёт статистики по схемам"""
        schemes_stats = {}
        for opp in opportunities:
            scheme = opp['scheme']
            if scheme not in schemes_stats:
                schemes_stats[scheme] = {'count': 0, 'max_spread': 0, 'total_profit': 0}
            schemes_stats[scheme]['count'] += 1
            schemes_stats[scheme]['max_spread'] = max(schemes_stats[scheme]['max_spread'], opp['spread'])
            schemes_stats[scheme]['total_profit'] += opp['profit']
        return schemes_stats