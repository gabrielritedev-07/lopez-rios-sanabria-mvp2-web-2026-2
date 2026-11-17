from django.urls import path

from .views import AbrirTurnoView, CerrarTurnoView, TurnoActualView, TurnosView

urlpatterns = [
    path("turno-actual/", TurnoActualView.as_view(), name="caja-turno-actual"),
    path("abrir/", AbrirTurnoView.as_view(), name="caja-abrir"),
    path("cerrar/", CerrarTurnoView.as_view(), name="caja-cerrar"),
    path("turnos/", TurnosView.as_view(), name="caja-turnos"),
]
