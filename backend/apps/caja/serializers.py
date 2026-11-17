from rest_framework import serializers

from .models import TurnoCaja


class AbrirTurnoSerializer(serializers.Serializer):
    baseInicial = serializers.IntegerField(
        source="base_inicial", min_value=0,
        error_messages={"min_value": "La base inicial no puede ser negativa."},
    )


class CerrarTurnoSerializer(serializers.Serializer):
    efectivoContado = serializers.IntegerField(
        source="efectivo_contado", min_value=0,
        error_messages={"min_value": "El efectivo contado no puede ser negativo."},
    )
    observaciones = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class TurnoCajaSerializer(serializers.ModelSerializer):
    usuario = serializers.CharField(source="usuario.username")
    abiertoEn = serializers.DateTimeField(source="abierto_en")
    cerradoEn = serializers.DateTimeField(source="cerrado_en")
    baseInicial = serializers.IntegerField(source="base_inicial")
    cantidadVentas = serializers.IntegerField(source="cantidad_ventas")
    ventasEfectivo = serializers.IntegerField(source="ventas_efectivo")
    ventasNequi = serializers.IntegerField(source="ventas_nequi")
    ventasDebe = serializers.IntegerField(source="ventas_debe")
    abonosEfectivo = serializers.IntegerField(source="abonos_efectivo")
    abonosNequi = serializers.IntegerField(source="abonos_nequi")
    reembolsosEfectivo = serializers.IntegerField(source="reembolsos_efectivo")
    efectivoEsperado = serializers.IntegerField(source="efectivo_esperado")
    efectivoContado = serializers.IntegerField(source="efectivo_contado", allow_null=True)
    resultado = serializers.CharField(read_only=True, allow_null=True)

    class Meta:
        model = TurnoCaja
        fields = [
            "id", "usuario", "estado", "abiertoEn", "cerradoEn", "baseInicial", "cantidadVentas",
            "ventasEfectivo", "ventasNequi", "ventasDebe", "abonosEfectivo", "abonosNequi",
            "reembolsosEfectivo", "efectivoEsperado", "efectivoContado", "diferencia", "resultado",
            "observaciones",
        ]
