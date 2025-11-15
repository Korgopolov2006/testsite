from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Load initial data from fixture'

    def handle(self, *args, **options):
        self.stdout.write('Loading data...')
        call_command('loaddata', 'data.json')
        self.stdout.write(self.style.SUCCESS('Data loaded successfully!'))
