# Построение диаграммы классов для вашего Django‑проекта (7 этапов)

Ниже — пошаговая методика, как из кода (`paint_shop_project/models.py`) получить поддерживаемую UML‑диаграмму классов, PNG и draw.io файл.

## Этап 1. Определите границы доменной модели
- Соберите ключевые сущности: `User`, `Role`, `Category`, `Manufacturer`, `Product`, `Cart`, `Order`, `OrderItem`, `OrderStatusHistory`, `Delivery`, `Payment`, `Review`, `Promotion`, `UserPromotion`, `LoyaltyCard`, `LoyaltyTransaction`, `Favorite`, `FavoriteCategory`, `CashbackTransaction`, `Store`, `SearchHistory`, `ViewHistory`, `Notification`, `EmployeeRating`, `SupportTicket`, `SupportResponse`, `SpecialSection`, `UserSpecialSection`, `PromoCode`, `Discount`, `ErrorLog`, `PhoneVerification`.
- Исключите не‑доменные элементы (формы, вьюхи, шаблоны).
Результат: перечень классов и их ответственность в системе.

## Этап 2. Зафиксируйте поля и инварианты классов
- Для каждого класса выпишите поля, типы и ограничения: required/optional, `choices`, `unique`, `unique_together`, `OneToOne`.
- Зафиксируйте смысловые инварианты (например, границы рейтинга 1..5, проценты скидок 0..50 и т.д.).
Результат: «паспорт» каждого класса (ядро полей и важные ограничения).

## Этап 3. Опишите связи и кардинальности
- Для каждой `ForeignKey`/`OneToOne`/`ManyToMany` определите направление и мощность (`1..1`, `1..*`, `*..*`).
- Уточните семантику владения и удаление (CASCADE/PROTECT/SET_NULL).
Результат: список всех связей между классами с кардинальностями.

## Этап 4. Соберите черновую диаграмму
- Отобразите классы (прямоугольники) и связи (стрелки) без идеальной раскладки.
- Сгруппируйте по подсистемам: Каталог, Корзина/Заказ, Платежи/Доставка, Лояльность/Кешбэк, Поддержка/Уведомления.
Результат: черновая диаграмма для дальнейшей шлифовки.

## Этап 5. Улучшите читаемость (уровни детализации)
- Слои: имя класса → ключевые поля → второстепенные поля.
- Сверните второстепенные поля в перегруженных местах, минимизируйте пересечения линий, примените auto‑layout.
Результат: диаграмма, которую удобно читать на одном экране.

## Этап 6. Автоматизируйте сборку PNG из кода
Вариант A (граф из моделей, быстро и нативно):
1) Установка:
```bash
pip install django-extensions pygraphviz
```
2) Добавьте в `paint_shop/settings.py`:
```python
INSTALLED_APPS += ["django_extensions"]
```
3) Сгенерируйте PNG из моделей:
```bash
python manage.py graph_models paint_shop_project -a -g -o docs/uml/class_diagram.png
```

Вариант B (Mermaid, удобно для CI):
- Исходник уже есть: `docs/uml/class_diagram.mmd` (сгенерирован на основе ваших моделей).
- Экспорт в PNG:
```bash
npx -y @mermaid-js/mermaid-cli -i docs/uml/class_diagram.mmd -o docs/uml/class_diagram.png -w 2400
```
Результат: воспроизводимый артефакт PNG из исходников проекта.

## Этап 7. Подготовьте draw.io и финальный экспорт
- Импортируйте Mermaid в draw.io: File → Import → выберите `docs/uml/class_diagram.mmd`.
- Отредактируйте расположение узлов, при необходимости добавьте комментарии.
- Сохраните как `docs/uml/class_diagram.drawio`.
- Экспорт PNG: File → Export As → PNG (опционально включите «Embed XML» для обратного импорта).
Результат: редактируемый draw.io файл + финальный PNG.

---

## Полезные команды (шпаргалка)
- Mermaid → PNG:
```bash
npx -y @mermaid-js/mermaid-cli -i docs/uml/class_diagram.mmd -o docs/uml/class_diagram.png -w 2400
```
- Django Extensions → PNG:
```bash
pip install django-extensions pygraphviz
python manage.py graph_models paint_shop_project -a -g -o docs/uml/class_diagram.png
```
- draw.io CLI (если установлен):
```bash
npx -y @drawio/cli -x -f png -o docs/uml/class_diagram.png docs/uml/class_diagram.drawio
```

## Советы
- Для больших схем ставьте ширину 2000–3000px.
- Храните исходники (`.mmd` / `.drawio`) в `docs/uml/` и собирайте PNG в CI/CD.
- Не перегружайте диаграмму второстепенными полями — держите акцент на связях и инвариантах.

