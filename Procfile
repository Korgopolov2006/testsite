web: gunicorn paint_shop.wsgi --log-file -
worker: celery -A paint_shop worker --loglevel=info
beat: celery -A paint_shop beat --loglevel=info
