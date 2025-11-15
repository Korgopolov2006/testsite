"""
Импорты для admin views
"""
try:
    from .database import DatabaseMaintenanceView
except ImportError:
    DatabaseMaintenanceView = None

try:
    from .dashboard import DashboardView, dashboard_api
except ImportError:
    DashboardView = None
    dashboard_api = None

try:
    from .notifications import NotificationsCenterView, notifications_api
except ImportError:
    NotificationsCenterView = None
    notifications_api = None

try:
    from .exports import ExportReportsView
except ImportError:
    ExportReportsView = None

try:
    from .performance import SlowQueriesView
except ImportError:
    SlowQueriesView = None

try:
    from .rfm import RFMAnalysisView
except ImportError:
    RFMAnalysisView = None

try:
    from .bulk_operations import BulkOperationsView, bulk_users_search
except ImportError:
    BulkOperationsView = None
    bulk_users_search = None

try:
    from .automation import OrderAutomationView
except ImportError:
    OrderAutomationView = None

try:
    from .warehouse_dashboard import WarehouseDashboardView, warehouse_dashboard_api
except ImportError:
    WarehouseDashboardView = None
    warehouse_dashboard_api = None

__all__ = [
    'DatabaseMaintenanceView',
    'DashboardView',
    'dashboard_api',
    'WarehouseDashboardView',
    'warehouse_dashboard_api',
    'NotificationsCenterView',
    'notifications_api',
    'ExportReportsView',
    'SlowQueriesView',
    'RFMAnalysisView',
    'BulkOperationsView',
    'bulk_users_search',
    'OrderAutomationView',
]
