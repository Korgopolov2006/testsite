from django.core.management.base import BaseCommand
from paint_shop_project.models import SpecialSection

class Command(BaseCommand):
    help = 'Создает специальные разделы (аналог Пушистого клуба)'

    def handle(self, *args, **options):
        sections_data = [
            {
                'name': '🐾 Пушистый клуб',
                'description': 'Специальные предложения для владельцев домашних животных. Двойной кешбэк на корма, игрушки и аксессуары для питомцев.',
                'icon': 'fas fa-paw',
                'color': '#ff6b9d',
                'cashback_multiplier': 2.0,
            },
            {
                'name': '👶 Детский мир',
                'description': 'Все для малышей и их родителей. Повышенный кешбэк на детское питание, подгузники и игрушки.',
                'icon': 'fas fa-baby',
                'color': '#4ecdc4',
                'cashback_multiplier': 1.8,
            },
            {
                'name': '🏃‍♀️ Здоровый образ жизни',
                'description': 'Спортивное питание, витамины и продукты для здорового образа жизни. Дополнительные бонусы за заботу о здоровье.',
                'icon': 'fas fa-dumbbell',
                'color': '#45b7d1',
                'cashback_multiplier': 1.5,
            },
            {
                'name': '🌱 Веганский выбор',
                'description': 'Растительные продукты, безглютеновые товары и экологически чистые продукты. Специальные предложения для веганов.',
                'icon': 'fas fa-leaf',
                'color': '#96ceb4',
                'cashback_multiplier': 1.7,
            },
            {
                'name': '🎂 Кондитерская',
                'description': 'Сладости, выпечка и кондитерские изделия. Дополнительные бонусы для любителей сладкого.',
                'icon': 'fas fa-birthday-cake',
                'color': '#feca57',
                'cashback_multiplier': 1.3,
            },
            {
                'name': '🍷 Гурман',
                'description': 'Премиальные продукты, деликатесы и изысканные товары. Специальные предложения для ценителей вкуса.',
                'icon': 'fas fa-wine-glass-alt',
                'color': '#8b5cf6',
                'cashback_multiplier': 1.6,
            },
        ]

        created_count = 0
        for section_data in sections_data:
            section, created = SpecialSection.objects.get_or_create(
                name=section_data['name'],
                defaults=section_data
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'Создан раздел: {section.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Раздел уже существует: {section.name}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'Создано {created_count} новых специальных разделов')
        )
