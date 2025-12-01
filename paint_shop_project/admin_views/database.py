from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.db.models import Count, DecimalField, F, Sum, ExpressionWrapper
from django.db.models.functions import TruncDay
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from ..admin_forms import (
    DatabaseBackupForm,
    DatabaseRestoreExistingForm,
    DatabaseRestoreUploadForm,
)
from ..models import DatabaseBackup, Order, OrderItem, User

logger = logging.getLogger(__name__)


BACKUP_DIR_NAME = "backups"
ALLOWED_BACKUP_EXTENSIONS = {".dump", ".sql", ".backup"}
AUTO_BACKUP_INTERVAL_HOURS = getattr(settings, "BACKUP_AUTO_INTERVAL_HOURS", 24)


def ensure_daily_backup() -> bool:
    """
    Проверяет, выполнялся ли автоматический бэкап за последние AUTO_BACKUP_INTERVAL_HOURS
    и при необходимости запускает его.
    """
    if not getattr(settings, "BACKUP_AUTO_ENABLED", True):
        return False
    
    last_backup = DatabaseBackup.objects.filter(
        operation="backup",
        status="success"
    ).order_by("-started_at").first()
    
    now = timezone.now()
    should_run = False
    if not last_backup:
        should_run = True
    else:
        delta = now - last_backup.started_at
        if delta >= timedelta(hours=AUTO_BACKUP_INTERVAL_HOURS):
            should_run = True
    
    if not should_run:
        return False
    
    try:
        folder_name = timezone.localtime(now).strftime("auto_%Y%m%d")
        perform_backup(
            label="auto",
            folder_name=folder_name,
            comment=f"Автоматический бэкап от {timezone.localtime(now).strftime('%d.%m.%Y %H:%M')}",
        )
        logger.info("Automatic backup created successfully")
        return True
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to create automatic backup: %s", exc)
        return False


def _get_db_settings() -> Dict[str, str]:
    return settings.DATABASES.get("default", {})


def _ensure_postgres(db_settings: Dict[str, str]) -> None:
    engine = db_settings.get("ENGINE", "")
    if "postgresql" not in engine:
        raise RuntimeError(
            _("Резервные копии через админку поддерживаются только для PostgreSQL.")
        )


def resolve_pg_command(command_name: str) -> str:
    """Определяет путь до бинарника PostgreSQL, учитывая настройки и окружение."""

    overrides = getattr(settings, "DATABASE_BACKUP_BIN", {})
    candidates: List[Path] = []

    if isinstance(overrides, dict) and command_name in overrides:
        candidates.append(Path(overrides[command_name]))

    env_key = f"{command_name.upper()}_PATH"
    env_value = os.environ.get(env_key)
    if env_value:
        candidates.append(Path(env_value))

    bin_dir = getattr(settings, "DATABASE_BACKUP_BIN_DIR", None)
    if bin_dir:
        candidates.append(Path(bin_dir) / command_name)
        candidates.append(Path(bin_dir) / f"{command_name}.exe")

    extra_dirs = getattr(settings, "DATABASE_BACKUP_BIN_DIRS", None)
    if extra_dirs:
        for directory in extra_dirs:
            candidates.append(Path(directory) / command_name)
            candidates.append(Path(directory) / f"{command_name}.exe")

    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)

    which_result = shutil.which(command_name)
    if which_result:
        return which_result

    exe_result = shutil.which(f"{command_name}.exe")
    if exe_result:
        return exe_result

    raise FileNotFoundError(
        _(
            "Команда %(command)s не найдена. Добавьте её в PATH или задайте в "
            "settings.DATABASE_BACKUP_BIN / DATABASE_BACKUP_BIN_DIR."
        )
        % {"command": command_name}
    )


def _get_backup_root() -> Path:
    media_root = getattr(settings, "MEDIA_ROOT", None)
    if not media_root:
        raise RuntimeError(
            _("MEDIA_ROOT не настроен. Укажите путь в настройках проекта." )
        )
    backup_dir = Path(media_root) / BACKUP_DIR_NAME
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def _format_bytes(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes} Б"
    for unit in ["КБ", "МБ", "ГБ", "ТБ"]:
        num_bytes /= 1024
        if num_bytes < 1024:
            return f"{num_bytes:.2f} {unit}"
    return f"{num_bytes:.2f} ПБ"


def _format_timedelta(delta) -> str:
    seconds = int(delta.total_seconds())
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts: List[str] = []
    if days:
        parts.append(_("%d д") % days)
    if hours:
        parts.append(_("%d ч") % hours)
    if minutes:
        parts.append(_("%d мин") % minutes)
    if not parts:
        parts.append(_("%d с") % seconds)
    return " ".join(parts)


def list_backup_files() -> List[dict]:
    backup_root = _get_backup_root()
    files: List[dict] = []
    file_candidates = [
        p
        for p in backup_root.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_BACKUP_EXTENSIONS
    ]
    for path in sorted(file_candidates, key=lambda p: p.stat().st_mtime, reverse=True):
        stat = path.stat()
        created_at = datetime.fromtimestamp(stat.st_mtime, tz=dt_timezone.utc)
        relative_path = path.relative_to(backup_root)
        parent = relative_path.parent
        files.append(
            {
                "name": path.name,
                "relative_path": relative_path.as_posix(),
                "folder": "" if parent == Path(".") else parent.as_posix(),
                "path": path,
                "size_bytes": stat.st_size,
                "size_display": _format_bytes(stat.st_size),
                "created_at": timezone.localtime(created_at),
            }
        )
    return files


def perform_backup(
    *,
    label: str | None = None,
    destination_dir: Path | None = None,
    folder_name: str | None = None,
    comment: str | None = None,
) -> Path:
    db_settings = _get_db_settings()
    _ensure_postgres(db_settings)

    database_name = db_settings.get("NAME")
    if not database_name:
        raise RuntimeError(_("Имя базы данных не указано."))

    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{label}" if label else ""

    base_dir = destination_dir or _get_backup_root()
    folder_slug = folder_name or "backup"
    backup_folder = base_dir / folder_slug / timestamp
    backup_folder.mkdir(parents=True, exist_ok=True)

    filename = f"{database_name}{suffix}.dump"
    backup_path = backup_folder / filename

    try:
        pg_dump_binary = resolve_pg_command("pg_dump")
    except FileNotFoundError as exc:
        raise RuntimeError(str(exc)) from exc

    command: List[str] = [pg_dump_binary, "--format=custom", "--blobs"]

    host = db_settings.get("HOST") or None
    port = db_settings.get("PORT") or None
    user = db_settings.get("USER") or None

    if host:
        command.extend(["--host", str(host)])
    if port:
        command.extend(["--port", str(port)])
    if user:
        command.extend(["--username", str(user)])

    command.extend(["--file", str(backup_path), str(database_name)])

    env = os.environ.copy()
    password = db_settings.get("PASSWORD")
    if password:
        env["PGPASSWORD"] = str(password)

    logger.info("Starting PostgreSQL backup to %s", backup_path)
    
    # Записываем начало операции в историю
    try:
        backup_record = DatabaseBackup(
            operation='backup',
            status='in_progress',
            file_path=str(backup_path),
            comment=comment or f"Резервная копия {label or 'автоматическая'}",
        )
        backup_record.save()
    except Exception as e:
        # Если ошибка с первичным ключом, исправляем последовательность и повторяем
        if 'paint_shop_project_databasebackup_pkey' in str(e) or 'duplicate key' in str(e).lower():
            logger.warning("Fixing sequence for DatabaseBackup due to key conflict")
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT setval('paint_shop_project_databasebackup_id_seq', 
                                  COALESCE((SELECT MAX(id) FROM paint_shop_project_databasebackup), 1), 
                                  true);
                """)
            backup_record = DatabaseBackup(
                operation='backup',
                status='in_progress',
                file_path=str(backup_path),
                comment=comment or f"Резервная копия {label or 'автоматическая'}",
            )
            backup_record.save()
        else:
            raise
    
    try:
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )

        if result.returncode != 0:
            if backup_path.exists():
                backup_path.unlink(missing_ok=True)  # type: ignore[arg-type]
            error_output = ""
            if result.stderr:
                error_output = result.stderr.strip()
            if not error_output and result.stdout:
                error_output = result.stdout.strip()
            if not error_output:
                error_output = _("Неизвестная ошибка восстановления базы данных")
            logger.error("pg_dump failed: %s", error_output)
            
            # Обновляем запись в истории
            backup_record.status = 'failed'
            backup_record.error_message = error_output
            backup_record.completed_at = timezone.now()
            backup_record.save()
            
            raise RuntimeError(_("pg_dump завершился с ошибкой: %s") % error_output)

        # Получаем размер файла
        file_size = backup_path.stat().st_size if backup_path.exists() else None
        
        # Обновляем запись в истории
        backup_record.status = 'success'
        backup_record.file_size = file_size
        backup_record.completed_at = timezone.now()
        backup_record.save()
        
        logger.info("Backup completed: %s", backup_path)
        return backup_path
    except Exception as exc:
        # Обновляем запись в истории при любой ошибке
        backup_record.status = 'failed'
        backup_record.error_message = str(exc)
        backup_record.completed_at = timezone.now()
        backup_record.save()
        raise


def _clean_database_before_restore(db_settings: Dict[str, str]) -> None:
    """Очищает базу данных перед восстановлением, безопасно удаляя все объекты с учетом зависимостей."""
    try:
        with connection.cursor() as cursor:
            # Отключаем проверку внешних ключей временно
            cursor.execute("SET session_replication_role = 'replica';")
            
            # Удаляем все таблицы с CASCADE для безопасного удаления зависимостей
            cursor.execute("""
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            
            # Включаем обратно проверку внешних ключей
            cursor.execute("SET session_replication_role = 'origin';")
            
            logger.info("Database cleaned successfully before restore")
    except Exception as exc:
        logger.warning("Failed to clean database before restore: %s", exc)
        # Не прерываем процесс, так как pg_restore может справиться сам


def _build_restore_command(file_path: Path, db_settings: Dict[str, str]) -> Tuple[List[str], dict]:
    host = db_settings.get("HOST") or None
    port = db_settings.get("PORT") or None
    user = db_settings.get("USER") or None
    database_name = db_settings.get("NAME")

    suffix = file_path.suffix.lower()
    if suffix == ".sql":
        try:
            psql_binary = resolve_pg_command("psql")
        except FileNotFoundError as exc:
            raise RuntimeError(str(exc)) from exc

        command: List[str] = [
            psql_binary,
            "--set",
            "ON_ERROR_STOP=on",
        ]
        if host:
            command.extend(["--host", str(host)])
        if port:
            command.extend(["--port", str(port)])
        if user:
            command.extend(["--username", str(user)])
        command.extend(["--dbname", str(database_name), "--file", str(file_path)])
    else:
        try:
            pg_restore_binary = resolve_pg_command("pg_restore")
        except FileNotFoundError as exc:
            raise RuntimeError(str(exc)) from exc

        command = [
            pg_restore_binary,
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            "--verbose",
        ]
        if host:
            command.extend(["--host", str(host)])
        if port:
            command.extend(["--port", str(port)])
        if user:
            command.extend(["--username", str(user)])
        command.extend(["--dbname", str(database_name), str(file_path)])

    env = os.environ.copy()
    password = db_settings.get("PASSWORD")
    if password:
        env["PGPASSWORD"] = str(password)
    return command, env


def perform_restore_from_file(
    file_path: Path,
    *,
    create_backup: bool = True,
    comment: str | None = None,
) -> None:
    if not file_path.exists():
        raise RuntimeError(_("Файл %s не найден.") % file_path.name)

    db_settings = _get_db_settings()
    _ensure_postgres(db_settings)

    # Записываем начало операции в историю
    try:
        restore_record = DatabaseBackup.objects.create(
            operation='restore',
            status='in_progress',
            file_path=str(file_path),
            comment=comment or f"Восстановление из {file_path.name}",
        )
    except Exception as e:
        # Если ошибка с первичным ключом, исправляем последовательность и повторяем
        if 'paint_shop_project_databasebackup_pkey' in str(e) or 'duplicate key' in str(e).lower():
            logger.warning("Fixing sequence for DatabaseBackup due to key conflict")
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT setval('paint_shop_project_databasebackup_id_seq', 
                                  COALESCE((SELECT MAX(id) FROM paint_shop_project_databasebackup), 1), 
                                  true);
                """)
            restore_record = DatabaseBackup.objects.create(
                operation='restore',
                status='in_progress',
                file_path=str(file_path),
                comment=comment or f"Восстановление из {file_path.name}",
            )
        else:
            raise
    
    if create_backup:
        try:
            perform_backup(label="pre_restore", comment="Автоматический бэкап перед восстановлением")
        except Exception as exc:  # pragma: no cover - безопасность
            logger.warning("Failed to create safety backup before restore: %s", exc)

    # Очищаем базу данных перед восстановлением для избежания конфликтов с зависимостями
    if file_path.suffix.lower() != ".sql":
        try:
            _clean_database_before_restore(db_settings)
        except Exception as exc:
            logger.warning("Failed to clean database before restore: %s", exc)
            # Продолжаем восстановление, так как pg_restore может справиться сам

    try:
        command, env = _build_restore_command(file_path, db_settings)

        logger.info("Starting database restore from %s", file_path)
        result = subprocess.run(
            command,
            env=env,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            check=False,
        )

        if result.returncode != 0:
            error_output = ""
            if result.stderr:
                error_output = result.stderr.strip()
            if not error_output and result.stdout:
                error_output = result.stdout.strip()
            if not error_output:
                error_output = _("Неизвестная ошибка восстановления базы данных")
            logger.error("Restore failed: %s", error_output)
            
            # Обновляем запись в истории
            restore_record.status = 'failed'
            restore_record.error_message = error_output
            restore_record.completed_at = timezone.now()
            restore_record.save()
            
            raise RuntimeError(_("Восстановление завершилось с ошибкой: %s") % error_output)

        # Обновляем запись в истории
        restore_record.status = 'success'
        restore_record.completed_at = timezone.now()
        restore_record.save()
        
        logger.info("Database restored successfully from %s", file_path)
    except Exception as exc:
        # Обновляем запись в истории при любой ошибке
        restore_record.status = 'failed'
        restore_record.error_message = str(exc)
        restore_record.completed_at = timezone.now()
        restore_record.save()
        raise


def fetch_database_metrics() -> Tuple[Dict[str, object], List[str]]:
    metrics: Dict[str, object] = {}
    errors: List[str] = []

    if connection.vendor != "postgresql":
        errors.append(
            _("Сбор метрик поддерживается только для PostgreSQL. Текущий движок: %s")
            % connection.vendor
        )
        return metrics, errors

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT version();")
            metrics["version"] = cursor.fetchone()[0]

            cursor.execute(
                "SELECT current_database(), pg_database_size(current_database());"
            )
            db_name, db_size = cursor.fetchone()
            metrics["database_name"] = db_name
            metrics["database_size_bytes"] = db_size
            metrics["database_size_display"] = _format_bytes(db_size)

            cursor.execute(
                "SELECT now() - pg_postmaster_start_time() AS uptime;"
            )
            uptime = cursor.fetchone()[0]
            if uptime is not None:
                metrics["uptime"] = _format_timedelta(uptime)

            cursor.execute(
                """
                SELECT state, COUNT(*)
                FROM pg_stat_activity
                WHERE datname = current_database()
                GROUP BY state
                ORDER BY state
                """
            )
            metrics["connections_by_state"] = [
                {"state": state or "unknown", "count": count}
                for state, count in cursor.fetchall()
            ]

            cursor.execute(
                """
                SELECT SUM(numbackends) AS connections
                FROM pg_stat_database
                WHERE datname = current_database()
                """
            )
            metrics["connections_total"] = cursor.fetchone()[0] or 0

            cursor.execute(
                """
                SELECT SUM(blks_hit) AS hit, SUM(blks_read) AS read
                FROM pg_stat_database
                WHERE datname = current_database()
                """
            )
            hit, read = cursor.fetchone()
            hit = hit or 0
            read = read or 0
            total = hit + read
            metrics["cache_hit_ratio"] = (hit / total * 100) if total else None

            cursor.execute(
                """
                SELECT relname,
                       pg_total_relation_size(relid) AS total_size,
                       pg_relation_size(relid) AS table_size,
                       pg_indexes_size(relid) AS index_size,
                       n_live_tup,
                       n_dead_tup,
                       last_autovacuum,
                       last_vacuum
                FROM pg_stat_user_tables
                ORDER BY total_size DESC
                LIMIT 10
                """
            )
            metrics["top_tables"] = [
                {
                    "table": row[0],
                    "total_size": _format_bytes(row[1]),
                    "table_size": _format_bytes(row[2]),
                    "index_size": _format_bytes(row[3]),
                    "live_rows": row[4],
                    "dead_rows": row[5],
                    "last_autovacuum": row[6],
                    "last_vacuum": row[7],
                }
                for row in cursor.fetchall()
            ]

    except Exception as exc:  # pragma: no cover - защита от неожиданных ошибок
        logger.exception("Failed to fetch database metrics")
        errors.append(str(exc))

    return metrics, errors


def gather_sales_metrics() -> Tuple[Dict[str, object], List[str]]:
    metrics: Dict[str, object] = {}
    errors: List[str] = []

    try:
        now = timezone.now()
        last_30_days = now - timedelta(days=30)
        last_7_days = now - timedelta(days=7)

        all_orders = Order.objects.all()
        delivered_orders = all_orders.filter(status="delivered")

        metrics["orders_total"] = all_orders.count()
        metrics["orders_delivered"] = delivered_orders.count()
        metrics["orders_last_30"] = all_orders.filter(order_date__gte=last_30_days).count()
        metrics["orders_in_progress"] = all_orders.exclude(status__in=("delivered", "cancelled")).count()

        revenue_total = delivered_orders.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        revenue_last_30 = delivered_orders.filter(order_date__gte=last_30_days).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        metrics["revenue_total"] = revenue_total
        metrics["revenue_last_30"] = revenue_last_30
        metrics["avg_order_value"] = (
            revenue_total / metrics["orders_delivered"]
            if metrics["orders_delivered"]
            else None
        )

        metrics["orders_by_status"] = list(
            all_orders.values("status").annotate(count=Count("id")).order_by("status")
        )

        repeat_customers = (
            all_orders.values("user")
            .annotate(order_count=Count("id"))
            .filter(order_count__gte=2)
            .count()
        )
        recent_customers = (
            all_orders.filter(order_date__gte=last_30_days)
            .values("user")
            .distinct()
            .count()
        )
        new_customers = User.objects.filter(date_joined__gte=last_30_days).count()

        metrics["repeat_customers"] = repeat_customers
        metrics["active_customers_last_30"] = recent_customers
        metrics["new_customers_last_30"] = new_customers

        revenue_expr = ExpressionWrapper(
            F("quantity") * F("price_per_unit"),
            output_field=DecimalField(max_digits=16, decimal_places=2)
        )

        top_products_qs = (
            OrderItem.objects.filter(order__status="delivered")
            .annotate(line_revenue=revenue_expr)
            .values("product__name")
            .annotate(
                quantity=Sum("quantity"),
                revenue=Sum("line_revenue"),
                orders=Count("order", distinct=True),
            )
            .order_by("-revenue", "-quantity")[:5]
        )
        metrics["top_products"] = [
            {
                "name": row["product__name"] or "—",
                "quantity": row["quantity"] or 0,
                "revenue": row["revenue"] or Decimal("0"),
                "orders": row["orders"] or 0,
            }
            for row in top_products_qs
        ]

        top_categories_qs = (
            OrderItem.objects.filter(order__status="delivered")
            .annotate(line_revenue=revenue_expr)
            .values("product__category__name")
            .annotate(
                quantity=Sum("quantity"),
                revenue=Sum("line_revenue"),
            )
            .order_by("-revenue", "-quantity")[:5]
        )
        metrics["top_categories"] = [
            {
                "name": row["product__category__name"] or "Без категории",
                "quantity": row["quantity"] or 0,
                "revenue": row["revenue"] or Decimal("0"),
            }
            for row in top_categories_qs
        ]

        daily_revenue_qs = (
            delivered_orders.filter(order_date__gte=last_7_days)
            .annotate(day=TruncDay("order_date"))
            .values("day")
            .annotate(revenue=Sum("total_amount"), orders=Count("id"))
            .order_by("day")
        )
        metrics["daily_revenue"] = [
            {
                "day": row["day"],
                "revenue": row["revenue"] or Decimal("0"),
                "orders": row["orders"],
            }
            for row in daily_revenue_qs
        ]

    except Exception as exc:  # pragma: no cover - защита на случай проблем БД
        logger.exception("Failed to fetch sales metrics")
        errors.append(str(exc))

    return metrics, errors


def test_database_connection() -> Dict[str, object]:
    result: Dict[str, object] = {}
    start = time.perf_counter()
    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
        elapsed = (time.perf_counter() - start) * 1000
        result["status"] = "ok"
        result["latency_ms"] = round(elapsed, 2)
    except Exception as exc:  # pragma: no cover
        result["status"] = "error"
        result["error"] = str(exc)
    return result


class DatabaseMaintenanceView(TemplateView):
    template_name = "admin/db_maintenance.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_staff:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        download = request.GET.get("download")
        if download:
            return self._download_backup(download)
        
        export_sql = request.GET.get("export_sql")
        if export_sql == "1":
            return self._export_sql_script()
        
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, _("Только суперпользователь может выполнять эти действия."))
            return redirect(self._self_url())

        action = request.POST.get("action")
        backup_files = list_backup_files()
        backup_choices = self._backup_choices(backup_files)

        if action == "create-backup":
            backup_form = DatabaseBackupForm(request.POST)
            if backup_form.is_valid():
                destination_choice = backup_form.cleaned_data["destination"]
                folder_name = backup_form.cleaned_data["folder_name"] or None
                custom_directory = backup_form.cleaned_data["custom_directory"]

                destination_dir = Path(custom_directory) if destination_choice == "custom" else None

                try:
                    backup_path = perform_backup(
                        destination_dir=destination_dir,
                        folder_name=folder_name,
                        comment=backup_form.cleaned_data.get("folder_name") or None,
                    )

                    if destination_choice == "custom":
                        messages.success(
                            request,
                            _("Резервная копия создана: %s") % backup_path,
                        )
                    else:
                        relative_path = backup_path.relative_to(_get_backup_root())
                        download_url = f"{self._self_url()}?download={relative_path.as_posix()}"
                        messages.success(
                            request,
                            format_html(
                                _(
                                    "Резервная копия создана в каталоге <code>{folder}</code>. "
                                    '<a href="{url}">Скачать</a>'
                                ),
                                folder=(relative_path.parent.as_posix() or "."),
                                url=download_url,
                            ),
                        )
                except Exception as exc:
                    messages.error(request, str(exc))
                return redirect(self._self_url())

            context = self.get_context_data(
                backup_form=backup_form,
                restore_upload_form=DatabaseRestoreUploadForm(),
                restore_existing_form=DatabaseRestoreExistingForm(backup_choices=backup_choices),
                backup_files=backup_files,
            )
            return self.render_to_response(context)

        if action == "test-connection":
            result = test_database_connection()
            if result.get("status") == "ok":
                latency = result.get("latency_ms")
                messages.success(
                    request,
                    _("Соединение успешно. Время отклика: %.2f мс") % latency,
                )
            else:
                messages.error(request, result.get("error") or _("Не удалось подключиться к БД."))
            return redirect(self._self_url())

        if action == "restore-upload":
            form = DatabaseRestoreUploadForm(request.POST, request.FILES)
            if form.is_valid():
                upload = form.cleaned_data["backup_file"]
                temp_dir = _get_backup_root() / "uploads"
                temp_dir.mkdir(parents=True, exist_ok=True)
                fd, temp_name = tempfile.mkstemp(prefix="restore_", dir=temp_dir)
                os.close(fd)
                temp_path = Path(temp_name)
                with temp_path.open("wb") as temp_file:
                    for chunk in upload.chunks():
                        temp_file.write(chunk)
                try:
                    perform_restore_from_file(
                        temp_path,
                        comment=f"Восстановление из загруженного файла: {upload.name}",
                    )
                    messages.success(
                        request,
                        _("База данных успешно восстановлена из загруженного файла."),
                    )
                except Exception as exc:
                    messages.error(request, str(exc))
                finally:
                    temp_path.unlink(missing_ok=True)  # type: ignore[arg-type]
                return redirect(self._self_url())

            existing_form = DatabaseRestoreExistingForm(backup_choices=backup_choices)
            context = self.get_context_data(
                restore_upload_form=form,
                restore_existing_form=existing_form,
                backup_form=DatabaseBackupForm(),
                backup_files=backup_files,
            )
            return self.render_to_response(context)

        if action == "restore-existing":
            form = DatabaseRestoreExistingForm(request.POST, backup_choices=backup_choices)
            if form.is_valid():
                backup_name = form.cleaned_data["backup_name"]
                backup_path = _get_backup_root() / backup_name  # backup_name уже относительный путь
                try:
                    perform_restore_from_file(
                        backup_path,
                        comment=f"Восстановление из выбранного бэкапа: {backup_name}",
                    )
                    messages.success(
                        request,
                        _("База данных восстановлена из бэкапа %s") % backup_name,
                    )
                except Exception as exc:
                    messages.error(request, str(exc))
                return redirect(self._self_url())

            upload_form = DatabaseRestoreUploadForm()
            context = self.get_context_data(
                restore_upload_form=upload_form,
                restore_existing_form=form,
                backup_form=DatabaseBackupForm(),
                backup_files=backup_files,
            )
            return self.render_to_response(context)

        messages.error(request, _("Неизвестное действие."))
        return redirect(self._self_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        backup_files = kwargs.get("backup_files") or list_backup_files()
        backup_choices = self._backup_choices(backup_files)

        auto_backup_triggered = ensure_daily_backup()
        metrics, metric_errors = fetch_database_metrics()
        sales_metrics, sales_metric_errors = gather_sales_metrics()
        backup_history = DatabaseBackup.objects.order_by('-started_at')[:20]
        last_backup = backup_history[0] if backup_history else None
        next_backup = None
        if last_backup:
            next_backup = last_backup.started_at + timedelta(hours=AUTO_BACKUP_INTERVAL_HOURS)

        context.update(
            {
                "title": _("Управление базой данных"),
                "metrics": metrics,
                "metric_errors": metric_errors,
                "sales_metrics": sales_metrics,
                "sales_metric_errors": sales_metric_errors,
                "backup_files": backup_files,
                "backup_choices": backup_choices,
                "backup_root": str(_get_backup_root()),
                "backup_form": kwargs.get("backup_form")
                or DatabaseBackupForm(),
                "restore_upload_form": kwargs.get("restore_upload_form")
                or DatabaseRestoreUploadForm(),
                "restore_existing_form": kwargs.get("restore_existing_form")
                or DatabaseRestoreExistingForm(backup_choices=backup_choices),
                "backup_history": backup_history,
                "last_backup": last_backup,
                "next_backup": next_backup,
                "auto_backup_triggered": auto_backup_triggered,
                "auto_backup_enabled": getattr(settings, "BACKUP_AUTO_ENABLED", True),
                "auto_backup_interval_hours": AUTO_BACKUP_INTERVAL_HOURS,
            }
        )
        return context

    def _download_backup(self, filename: str) -> HttpResponse:
        backup_root = _get_backup_root()
        target = (backup_root / filename).resolve()
        if not str(target).startswith(str(backup_root.resolve())) or not target.exists():
            raise Http404
        return FileResponse(
            target.open("rb"),
            filename=target.name,
            as_attachment=True,
        )
    
    def _export_sql_script(self) -> HttpResponse:
        """Экспортирует базу данных в SQL скрипт"""
        db_settings = _get_db_settings()
        _ensure_postgres(db_settings)
        
        database_name = db_settings.get("NAME")
        if not database_name:
            raise RuntimeError(_("Имя базы данных не указано."))
        
        try:
            pg_dump_binary = resolve_pg_command("pg_dump")
        except FileNotFoundError as exc:
            raise RuntimeError(str(exc)) from exc
        
        # Создаем временные файлы для SQL скрипта
        import tempfile
        schema_file = tempfile.NamedTemporaryFile(mode='w+', suffix='_schema.sql', delete=False)
        schema_path = Path(schema_file.name)
        schema_file.close()
        
        data_file = tempfile.NamedTemporaryFile(mode='w+', suffix='_data.sql', delete=False)
        data_path = Path(data_file.name)
        data_file.close()
        
        final_file = tempfile.NamedTemporaryFile(mode='w+', suffix='.sql', delete=False)
        final_path = Path(final_file.name)
        final_file.close()
        
        host = db_settings.get("HOST") or None
        port = db_settings.get("PORT") or None
        user = db_settings.get("USER") or None
        
        env = os.environ.copy()
        password = db_settings.get("PASSWORD")
        if password:
            env["PGPASSWORD"] = str(password)
        
        try:
            # Базовые параметры команды
            base_params = []
            if host:
                base_params.extend(["--host", str(host)])
            if port:
                base_params.extend(["--port", str(port)])
            if user:
                base_params.extend(["--username", str(user)])
            
            # 1. Экспортируем структуру (схему) - сначала
            logger.info("Exporting database schema to SQL script")
            schema_command = [pg_dump_binary, "--format=plain", "--no-owner", "--no-privileges", "--schema-only"]
            schema_command.extend(base_params)
            schema_command.extend(["--file", str(schema_path), str(database_name)])
            
            result = subprocess.run(
                schema_command,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                logger.error("SQL schema export failed: %s", error_msg)
                raise RuntimeError(f"Ошибка экспорта структуры SQL: {error_msg}")
            
            # 2. Экспортируем данные - потом
            logger.info("Exporting database data to SQL script")
            data_command = [pg_dump_binary, "--format=plain", "--no-owner", "--no-privileges", "--data-only", "--disable-triggers"]
            data_command.extend(base_params)
            data_command.extend(["--file", str(data_path), str(database_name)])
            
            result = subprocess.run(
                data_command,
                env=env,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or "Unknown error"
                logger.error("SQL data export failed: %s", error_msg)
                raise RuntimeError(f"Ошибка экспорта данных SQL: {error_msg}")
            
            # 3. Объединяем: сначала структура, потом данные
            with final_path.open("wb") as final:
                # Записываем структуру
                if schema_path.exists():
                    with schema_path.open("rb") as schema:
                        final.write(schema.read())
                        final.write(b"\n\n-- ============================================\n")
                        final.write(b"-- DATA\n")
                        final.write(b"-- ============================================\n\n")
                
                # Записываем данные
                if data_path.exists():
                    with data_path.open("rb") as data:
                        final.write(data.read())
            
            # Читаем объединенный SQL файл и возвращаем как ответ
            with final_path.open("rb") as sql_file:
                response = HttpResponse(sql_file.read(), content_type="text/plain; charset=utf-8")
                timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
                filename = f"{database_name}_export_{timestamp}.sql"
                response["Content-Disposition"] = f'attachment; filename="{filename}"'
                return response
        finally:
            # Удаляем временные файлы
            for path in [schema_path, data_path, final_path]:
                if path.exists():
                    try:
                        path.unlink()
                    except Exception:
                        pass

    def _backup_choices(self, backup_files: Iterable[dict]) -> List[Tuple[str, str]]:
        return [
            (
                item["relative_path"],
                f"{(item['folder'] + '/' if item['folder'] else '')}{item['name']} — {item['size_display']}",
            )
            for item in backup_files
        ]

    def _self_url(self) -> str:
        return reverse("admin:database-maintenance")

