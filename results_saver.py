import json
import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from configs import RESULTS_DIR


class ResultsSaver:
    """Класс для сохранения результатов внутрибиржевого арбитража"""

    def __init__(self, results_dir: Path = RESULTS_DIR):
        self.results_dir = results_dir
        self.results_dir.mkdir(exist_ok=True)

    def save_opportunities(
            self,
            opportunities: List[Dict],
            start_amount: float,
            min_spread: float,
            execution_time: float,
            save_formats: List[str] = ['json', 'txt', 'csv', 'html']
    ) -> Dict[str, Path]:
        """Сохраняет результаты в указанных форматах"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_files = {}

        # Метаданные
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'start_amount': start_amount,
            'min_spread': min_spread,
            'execution_time': execution_time,
            'total_opportunities': len(opportunities),
            'arbitrage_type': 'internal_bybit'
        }

        # Сохранение в JSON
        if 'json' in save_formats:
            json_path = self.results_dir / f'internal_arbitrage_{timestamp}.json'
            self._save_json(json_path, opportunities, metadata)
            saved_files['json'] = json_path

        # Сохранение в TXT
        if 'txt' in save_formats:
            txt_path = self.results_dir / f'internal_arbitrage_{timestamp}.txt'
            self._save_txt(txt_path, opportunities, metadata)
            saved_files['txt'] = txt_path

        # Сохранение в CSV
        if 'csv' in save_formats:
            csv_path = self.results_dir / f'internal_arbitrage_{timestamp}.csv'
            self._save_csv(csv_path, opportunities, metadata)
            saved_files['csv'] = csv_path

        # Сохранение в HTML
        if 'html' in save_formats:
            html_path = self.results_dir / f'internal_arbitrage_{timestamp}.html'
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
            f.write("🚀 CRYPTO ARBITRAGE BOT v6.0 — ВНУТРИБИРЖЕВОЙ АРБИТРАЖ НА BYBIT\n")
            f.write("=" * 100 + "\n\n")

            # Метаданные
            f.write(f"📅 Дата и время: {metadata['timestamp']}\n")
            f.write(f"💰 Начальная сумма: ${metadata['start_amount']:.2f}\n")
            f.write(f"📊 Минимальный спред: {metadata['min_spread']}%\n")
            f.write(f"⏱️  Время выполнения: {metadata['execution_time']:.2f} сек\n")
            f.write(f"🎯 Найдено возможностей: {metadata['total_opportunities']}\n\n")

            # Статистика по типам
            if opportunities:
                types_stats = self._calculate_types_stats(opportunities)
                f.write("=" * 100 + "\n")
                f.write("📈 СТАТИСТИКА ПО ТИПАМ\n")
                f.write("=" * 100 + "\n\n")

                type_names = {
                    'triangular': '🔺 Треугольный (3 сделки)',
                    'quadrilateral': '🔶 Четырехугольный (4 сделки)',
                    'bestchange_arbitrage': '🔀 Через BestChange'
                }

                for opp_type, stats in sorted(types_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                    type_name = type_names.get(opp_type, opp_type)
                    f.write(f"{type_name}\n")
                    f.write(f"  • Найдено: {stats['count']} возможностей\n")
                    f.write(f"  • Макс. спред: {stats['max_spread']:.4f}%\n")
                    f.write(f"  • Средний спред: {stats['avg_spread']:.4f}%\n")
                    f.write(f"  • Суммарная прибыль: ${stats['total_profit']:.2f}\n\n")

            # Детальный список возможностей
            if opportunities:
                f.write("\n" + "=" * 100 + "\n")
                f.write(f"🎯 СПИСОК АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ\n")
                f.write("=" * 100 + "\n\n")

                for idx, opp in enumerate(opportunities, 1):
                    icon = "🔺" if opp['type'] == 'triangular' else ("🔶" if opp['type'] == 'quadrilateral' else "🔀")
                    f.write(f"{icon} #{idx} | Спред: {opp['spread']:.4f}% | Прибыль: ${opp['profit']:.4f}\n")
                    f.write(f"    Тип: {opp.get('type', 'N/A')}\n")
                    f.write(f"    Схема: {opp['scheme']}\n")
                    f.write(f"    Путь: {opp['path']}\n")
                    f.write(f"    Начальная сумма: ${opp['initial']:.2f} → Финальная: ${opp['final']:.2f}\n")
                    f.write(f"    Детали:\n")
                    for step in opp['steps']:
                        f.write(f"       {step}\n")
                    f.write("\n")

            # Предупреждения
            f.write("\n" + "=" * 100 + "\n")
            f.write("⚠️  ВАЖНЫЕ ЗАМЕЧАНИЯ\n")
            f.write("=" * 100 + "\n\n")
            f.write("1. Указанные спреды НЕ учитывают комиссии биржи (~0.1% за сделку)\n")
            f.write("2. Треугольный арбитраж: 3 сделки = ~0.3% комиссий\n")
            f.write("3. Четырехугольный арбитраж: 4 сделки = ~0.4% комиссий\n")
            f.write("4. Проскальзывание цены может съесть часть прибыли\n")
            f.write("5. Все сделки должны выполняться последовательно и быстро\n")
            f.write("6. Используйте монеты с высокой ликвидностью для минимизации проскальзывания\n")
            f.write("7. Всегда проверяйте актуальность данных перед совершением сделок!\n")

    def _save_csv(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в CSV формате"""
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)

            # Заголовки
            writer.writerow([
                'Rank',
                'Type',
                'Scheme',
                'Path',
                'Spread %',
                'Profit $',
                'Initial $',
                'Final $',
                'Num Coins',
                'Coins',
                'Steps'
            ])

            # Данные
            for idx, opp in enumerate(opportunities, 1):
                opp_type = opp.get('type', 'N/A')
                coins = ' → '.join(opp.get('coins', []))
                num_coins = len(opp.get('coins', []))
                steps = ' | '.join(opp.get('steps', []))

                writer.writerow([
                    idx,
                    opp_type,
                    opp['scheme'],
                    opp['path'],
                    f"{opp['spread']:.4f}",
                    f"{opp['profit']:.4f}",
                    f"{opp['initial']:.2f}",
                    f"{opp['final']:.2f}",
                    num_coins,
                    coins,
                    steps
                ])

    def _extract_rates_from_opportunity(self, opp: Dict) -> List[Dict]:
        """Извлекает курсы из возможности арбитража"""
        rates = []

        # Для BestChange арбитража используем готовые данные
        if opp['type'] == 'bestchange_arbitrage':
            coin_a = opp['coins'][0] if len(opp['coins']) > 0 else 'UNKNOWN'
            coin_b = opp['coins'][1] if len(opp['coins']) > 1 else 'UNKNOWN'

            # Используем данные напрямую из opportunity
            bybit_rate_a = opp.get('bybit_rate_a', 0)
            exchange_rate = opp.get('exchange_rate', 0)
            bybit_rate_b = opp.get('bybit_rate_b', 0)

            rates = [
                {'from': 'USDT', 'to': coin_a, 'rate': bybit_rate_a},
                {'from': coin_a, 'to': coin_b, 'rate': exchange_rate},
                {'from': coin_b, 'to': 'USDT', 'rate': bybit_rate_b}
            ]

            return rates

        # Для треугольного и четырехугольного арбитража
        path_parts = opp['path'].split(' → ')

        # Треугольный арбитраж: USDT → A → B → USDT
        if opp['type'] == 'triangular' and len(path_parts) == 4:
            coin_a = path_parts[1]
            coin_b = path_parts[2]

            # Извлекаем курсы из steps с защитой от ошибок
            for step in opp['steps']:
                try:
                    if 'Купить' in step and coin_a in step and 'USDT' in step:
                        # USDT -> A: ищем цену после "по цене $"
                        if 'по цене $' in step:
                            rate_str = step.split('по цене $')[1].split(')')[0].strip()
                            rates.append({'from': 'USDT', 'to': coin_a, 'rate': float(rate_str)})

                    elif coin_a in step and coin_b in step and 'Обмен' in step:
                        # A -> B: ищем курс после "(курс"
                        if '(курс' in step or 'курс:' in step:
                            rate_str = step.split('курс')[1].strip()
                            if rate_str.startswith(':'):
                                rate_str = rate_str[1:].strip()
                            rate_str = rate_str.split(')')[0].strip()
                            rates.append({'from': coin_a, 'to': coin_b, 'rate': float(rate_str)})

                    elif 'Продать' in step and coin_b in step and 'USDT' in step:
                        # B -> USDT: ищем цену после "по цене $"
                        if 'по цене $' in step:
                            rate_str = step.split('по цене $')[1].split(')')[0].strip()
                            rates.append({'from': coin_b, 'to': 'USDT', 'rate': float(rate_str)})
                except (ValueError, IndexError, AttributeError):
                    # Если не удалось извлечь курс, пропускаем
                    continue

        # Четырехугольный арбитраж: USDT → A → B → C → USDT
        elif opp['type'] == 'quadrilateral' and len(path_parts) == 5:
            # Для четырехугольного используем упрощённый подход
            # Извлекаем из шагов с обработкой ошибок
            for step in opp['steps']:
                try:
                    if 'по цене $' in step:
                        rate_str = step.split('по цене $')[1].split(')')[0].strip()
                        # Определяем from и to из текста
                        parts = step.split(' ')
                        if 'Купить' in step:
                            rates.append({'from': 'USDT', 'to': parts[1], 'rate': float(rate_str)})
                        elif 'Продать' in step:
                            coin = [p for p in parts if p.isupper() and len(p) <= 10][0]
                            rates.append({'from': coin, 'to': 'USDT', 'rate': float(rate_str)})
                    elif 'курс' in step:
                        rate_str = step.split('курс')[1].strip()
                        if rate_str.startswith(':'):
                            rate_str = rate_str[1:].strip()
                        rate_str = rate_str.split(')')[0].strip()
                        rates.append({'from': 'A', 'to': 'B', 'rate': float(rate_str)})
                except (ValueError, IndexError, AttributeError):
                    continue

        return rates

    def _save_html(self, path: Path, opportunities: List[Dict], metadata: Dict):
        """Сохранение в HTML формате с редактируемыми курсами"""

        type_names = {
            'triangular': '🔺 Треугольный',
            'quadrilateral': '🔶 Четырехугольный',
            'bestchange_arbitrage': '🔀 Через BestChange'
        }

        type_colors = {
            'triangular': '#28a745',
            'quadrilateral': '#fd7e14',
            'bestchange_arbitrage': '#17a2b8'
        }

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
        .type-stat {{ padding: 15px; margin: 10px 0; background: #f8f9fa; border-radius: 5px; }}
        .opportunities {{ padding: 20px; }}
        .opportunity {{ margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 5px; border-left: 4px solid #667eea; }}
        .opportunity-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; flex-wrap: wrap; gap: 10px; }}
        .opportunity-rank {{ font-size: 24px; font-weight: bold; color: #667eea; }}
        .spread {{ font-size: 20px; font-weight: bold; color: #28a745; }}
        .profit {{ font-size: 18px; color: #28a745; }}
        .type-badge {{ display: inline-block; padding: 5px 15px; color: white; border-radius: 20px; font-size: 12px; margin-left: 10px; }}
        .scheme-badge {{ display: inline-block; padding: 5px 15px; background: #6c757d; color: white; border-radius: 20px; font-size: 11px; }}
        .path-container {{ margin: 15px 0; padding: 15px; background: white; border-radius: 5px; }}
        .path-item {{ display: inline-flex; align-items: center; margin: 5px 0; }}
        .coin {{ font-weight: bold; color: #333; padding: 5px 10px; background: #e9ecef; border-radius: 3px; }}
        .arrow-container {{ margin: 0 10px; display: inline-flex; flex-direction: column; align-items: center; }}
        .arrow {{ font-size: 20px; color: #667eea; }}
        .rate-input {{ width: 120px; padding: 5px 8px; border: 2px solid #667eea; border-radius: 4px; text-align: center; font-size: 14px; font-weight: bold; }}
        .rate-input:focus {{ outline: none; border-color: #764ba2; background: #f0f8ff; }}
        .result-box {{ margin-top: 15px; padding: 15px; background: #d4edda; border: 2px solid #28a745; border-radius: 5px; }}
        .result-value {{ font-size: 18px; font-weight: bold; color: #155724; }}
        .steps {{ margin-top: 15px; padding-left: 20px; }}
        .step {{ padding: 8px 0; border-bottom: 1px solid #e0e0e0; }}
        .step:last-child {{ border-bottom: none; }}
        .warning {{ background: #fff3cd; padding: 20px; margin: 20px; border-radius: 5px; border-left: 4px solid #ffc107; }}
        .warning h3 {{ color: #856404; margin-bottom: 10px; }}
        .warning ul {{ padding-left: 20px; }}
        .warning li {{ margin: 5px 0; color: #856404; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Crypto Arbitrage Bot v7.0</h1>
            <p>Интерактивный анализ арбитражных возможностей</p>
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

        # Статистика по типам
        if opportunities:
            types_stats = self._calculate_types_stats(opportunities)
            html_content += """
        <div class="stats">
            <h2>📈 Статистика по типам арбитража</h2>
"""
            for opp_type, stats in sorted(types_stats.items(), key=lambda x: x[1]['max_spread'], reverse=True):
                type_name = type_names.get(opp_type, opp_type)
                color = type_colors.get(opp_type, '#6c757d')
                html_content += f"""
            <div class="type-stat" style="border-left: 4px solid {color};">
                <strong>{type_name}</strong><br>
                Найдено: {stats['count']} возможностей | 
                Макс. спред: {stats['max_spread']:.4f}% | 
                Средний спред: {stats['avg_spread']:.4f}% |
                Суммарная прибыль: ${stats['total_profit']:.2f}
            </div>
"""
            html_content += """
        </div>
"""

        # Список возможностей
        if opportunities:
            html_content += """
        <div class="opportunities">
            <h2>🎯 Список арбитражных возможностей</h2>
"""
            for idx, opp in enumerate(opportunities, 1):
                opp_type = opp.get('type', 'unknown')
                type_name = type_names.get(opp_type, opp_type)
                color = type_colors.get(opp_type, '#6c757d')

                # Парсим путь
                path_parts = opp['path'].split(' → ')
                rates = self._extract_rates_from_opportunity(opp)

                # Создаем интерактивный путь с редактируемыми курсами
                path_html = '<div class="path-container"><div style="font-weight: bold; margin-bottom: 10px;">Путь с курсами обмена:</div>'

                for i, part in enumerate(path_parts):
                    path_html += f'<span class="coin">{part}</span>'
                    if i < len(path_parts) - 1:
                        rate_val = rates[i]['rate'] if i < len(rates) else 0
                        path_html += f'''
                        <div class="arrow-container">
                            <div class="arrow">↓</div>
                            <input type="number" 
                                   class="rate-input" 
                                   data-opp-id="{idx}" 
                                   data-rate-index="{i}"
                                   value="{rate_val:.8f}" 
                                   step="0.00000001"
                                   onchange="recalculate({idx})">
                        </div>
                        '''

                path_html += '</div>'

                steps_html = ""
                for step in opp['steps']:
                    steps_html += f'<div class="step">{step}</div>'

                html_content += f"""
            <div class="opportunity" style="border-left: 4px solid {color};" id="opp-{idx}">
                <div class="opportunity-header">
                    <div>
                        <span class="opportunity-rank">#{idx}</span>
                        <span class="type-badge" style="background-color: {color};">{type_name}</span>
                        <span class="scheme-badge">{opp['scheme']}</span>
                    </div>
                    <div>
                        <span class="spread" id="spread-{idx}">{opp['spread']:.4f}%</span>
                        <span class="profit" id="profit-{idx}"> | Прибыль: ${opp['profit']:.4f}</span>
                    </div>
                </div>

                {path_html}

                <div class="result-box">
                    <div class="result-value" id="result-{idx}">
                        ${opp['initial']:.2f} → $<span id="final-{idx}">{opp['final']:.2f}</span>
                    </div>
                </div>

                <div class="steps">
                    <strong>Детали операций:</strong>
                    {steps_html}
                </div>

                <script>
                    window['opp_{idx}_data'] = {{
                        initial: {opp['initial']},
                        rates: {json.dumps([r['rate'] for r in rates])},
                        pathParts: {json.dumps(path_parts)}
                    }};
                </script>
            </div>
"""
            html_content += """
        </div>
"""

        # JavaScript для пересчёта
        html_content += """
        <script>
            function recalculate(oppId) {
                const data = window['opp_' + oppId + '_data'];
                const inputs = document.querySelectorAll(`input[data-opp-id="${oppId}"]`);

                let amount = data.initial;
                const rates = [];

                inputs.forEach(input => {
                    rates.push(parseFloat(input.value));
                });

                // Пересчитываем по цепочке
                for (let i = 0; i < rates.length; i++) {
                    if (i === 0) {
                        // USDT -> Coin A
                        amount = amount / rates[i];
                    } else if (i === rates.length - 1) {
                        // Last Coin -> USDT
                        amount = amount * rates[i];
                    } else {
                        // Coin -> Coin
                        amount = amount * rates[i];
                    }
                }

                const profit = amount - data.initial;
                const spread = ((amount - data.initial) / data.initial) * 100;

                // Обновляем UI
                document.getElementById('final-' + oppId).textContent = amount.toFixed(2);
                document.getElementById('spread-' + oppId).textContent = spread.toFixed(4) + '%';
                document.getElementById('profit-' + oppId).textContent = ' | Прибыль: $' + profit.toFixed(4);

                // Меняем цвет в зависимости от прибыли
                const spreadEl = document.getElementById('spread-' + oppId);
                const profitEl = document.getElementById('profit-' + oppId);

                if (spread > 0) {
                    spreadEl.style.color = '#28a745';
                    profitEl.style.color = '#28a745';
                } else {
                    spreadEl.style.color = '#dc3545';
                    profitEl.style.color = '#dc3545';
                }
            }
        </script>
"""

        # Предупреждения
        html_content += """
        <div class="warning">
            <h3>⚠️ Важные замечания</h3>
            <ul>
                <li>Вы можете изменить курсы обмена, чтобы актуализировать расчёты</li>
                <li>Указанные спреды НЕ учитывают комиссии биржи (~0.1% за сделку)</li>
                <li>Треугольный арбитраж: 3 сделки = ~0.3% комиссий</li>
                <li>Четырехугольный арбитраж: 4 сделки = ~0.4% комиссий</li>
                <li>Проскальзывание цены может съесть часть прибыли</li>
                <li>Все сделки должны выполняться последовательно и максимально быстро</li>
                <li>Используйте монеты с высокой ликвидностью (BTC, ETH, BNB) для минимизации проскальзывания</li>
                <li>Рекомендуется искать спреды > 1% для покрытия всех издержек</li>
                <li>Цены постоянно меняются - всегда проверяйте актуальность перед сделкой!</li>
            </ul>
        </div>
    </div>
</body>
</html>"""

        with open(path, 'w', encoding='utf-8') as f:
            f.write(html_content)

    def _calculate_types_stats(self, opportunities: List[Dict]) -> Dict:
        """Подсчёт статистики по типам арбитража"""
        types_stats = {}
        for opp in opportunities:
            opp_type = opp.get('type', 'unknown')
            if opp_type not in types_stats:
                types_stats[opp_type] = {
                    'count': 0,
                    'max_spread': 0,
                    'total_spread': 0,
                    'total_profit': 0
                }
            types_stats[opp_type]['count'] += 1
            types_stats[opp_type]['max_spread'] = max(types_stats[opp_type]['max_spread'], opp['spread'])
            types_stats[opp_type]['total_spread'] += opp['spread']
            types_stats[opp_type]['total_profit'] += opp['profit']

        # Вычисляем средний спред
        for opp_type in types_stats:
            count = types_stats[opp_type]['count']
            if count > 0:
                types_stats[opp_type]['avg_spread'] = types_stats[opp_type]['total_spread'] / count
            else:
                types_stats[opp_type]['avg_spread'] = 0

        return types_stats