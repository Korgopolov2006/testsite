"""
Мониторинг медленных запросов БД
"""
import logging
from typing import Dict, List

from django.contrib.auth.decorators import user_passes_test
from django.db import connection
from django.utils.decorators import method_decorator
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from ..admin_views.database import _get_db_settings

logger = logging.getLogger(__name__)


def is_staff(user):
    return user.is_staff


@method_decorator(user_passes_test(is_staff), name='dispatch')
class SlowQueriesView(TemplateView):
    """Мониторинг медленных запросов PostgreSQL"""
    template_name = 'admin/slow_queries.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        db_settings = _get_db_settings()
        engine = db_settings.get('ENGINE', '')
        
        slow_queries = []
        db_stats = {}
        
        if 'postgresql' in engine:
            try:
                with connection.cursor() as cursor:
                    # Получаем медленные запросы из pg_stat_statements (если включен)
                    try:
                        cursor.execute("""
                            SELECT 
                                query,
                                calls,
                                total_exec_time,
                                mean_exec_time,
                                max_exec_time
                            FROM pg_stat_statements
                            ORDER BY mean_exec_time DESC
                            LIMIT 20
                        """)
                        
                        slow_queries = [
                            {
                                'query': row[0][:200] + '...' if len(row[0]) > 200 else row[0],
                                'full_query': row[0],
                                'calls': row[1],
                                'total_time': float(row[2]),
                                'mean_time': float(row[3]),
                                'max_time': float(row[4]),
                            }
                            for row in cursor.fetchall()
                        ]
                    except Exception:
                        # pg_stat_statements может быть не включен
                        slow_queries = []
                    
                    # Статистика по таблицам
                    cursor.execute("""
                        SELECT 
                            schemaname,
                            tablename,
                            n_live_tup,
                            n_dead_tup,
                            last_vacuum,
                            last_autovacuum,
                            last_analyze,
                            last_autoanalyze
                        FROM pg_stat_user_tables
                        ORDER BY n_live_tup DESC
                        LIMIT 20
                    """)
                    
                    db_stats['tables'] = [
                        {
                            'schema': row[0],
                            'table': row[1],
                            'live_tuples': row[2],
                            'dead_tuples': row[3],
                            'last_vacuum': row[4],
                            'last_autovacuum': row[5],
                            'last_analyze': row[6],
                            'last_autoanalyze': row[7],
                        }
                        for row in cursor.fetchall()
                    ]
                    
                    # Активные запросы
                    cursor.execute("""
                        SELECT 
                            pid,
                            usename,
                            application_name,
                            state,
                            query_start,
                            state_change,
                            wait_event_type,
                            wait_event,
                            query
                        FROM pg_stat_activity
                        WHERE state != 'idle'
                        AND pid != pg_backend_pid()
                        ORDER BY query_start
                    """)
                    
                    db_stats['active_queries'] = [
                        {
                            'pid': row[0],
                            'user': row[1],
                            'app': row[2],
                            'state': row[3],
                            'query_start': row[4],
                            'query': row[8][:200] + '...' if row[8] and len(row[8]) > 200 else (row[8] or ''),
                        }
                        for row in cursor.fetchall()
                    ]
                    
            except Exception as exc:
                logger.error(f"Error fetching slow queries: {exc}")
                slow_queries = []
                db_stats = {}
        
        context.update({
            'title': _('Мониторинг производительности БД'),
            'slow_queries': slow_queries,
            'db_stats': db_stats,
            'has_pg_stat_statements': len(slow_queries) > 0,
        })
        
        return context




