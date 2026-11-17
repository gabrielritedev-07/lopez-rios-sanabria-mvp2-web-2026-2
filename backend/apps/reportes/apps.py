from django.apps import AppConfig


class ReportesConfig(AppConfig):
    """Reportes de solo lectura (Fase 4). No define tablas: consulta las de otras apps."""

    name = "apps.reportes"
    label = "reportes"
    verbose_name = "Reportes"
