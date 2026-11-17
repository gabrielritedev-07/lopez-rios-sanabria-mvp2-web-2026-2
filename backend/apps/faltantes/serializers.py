from rest_framework import serializers

from apps.catalogo.models import Producto, Proveedor

from .models import Faltante


class FaltanteEntradaSerializer(serializers.Serializer):
    productoId = serializers.PrimaryKeyRelatedField(
        source="producto",
        queryset=Producto.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "El producto seleccionado no existe."},
    )
    # Descripción en texto cuando el producto no existe en el catálogo.
    nombre = serializers.CharField(max_length=150, required=False, allow_blank=True)
    cantidad = serializers.IntegerField(
        min_value=1,
        required=False,
        default=1,
        error_messages={"min_value": "La cantidad solicitada debe ser al menos 1."},
    )
    tipo = serializers.ChoiceField(
        choices=Faltante.Tipo.choices,
        error_messages={
            "required": "Indica si el producto es inexistente o está agotado.",
            "invalid_choice": "El tipo debe ser inexistente o agotado.",
        },
    )
    proveedorId = serializers.PrimaryKeyRelatedField(
        source="proveedor",
        queryset=Proveedor.objects.all(),
        required=False,
        allow_null=True,
        error_messages={"does_not_exist": "El proveedor seleccionado no existe."},
    )

    def validate(self, attrs):
        producto = attrs.get("producto")
        nombre = (attrs.get("nombre") or "").strip()
        tipo = attrs["tipo"]

        if tipo == Faltante.Tipo.AGOTADO and producto is None:
            raise serializers.ValidationError({
                "productoId": "Para un producto agotado selecciona el producto del catálogo."
            })
        if tipo == Faltante.Tipo.INEXISTENTE and producto is not None:
            raise serializers.ValidationError({
                "tipo": "Ese producto ya existe en el catálogo; regístralo como agotado."
            })
        if producto is None and not nombre:
            raise serializers.ValidationError({"nombre": "Describe el producto que pidió el cliente."})

        attrs["nombre"] = nombre or producto.nombre
        return attrs


class FaltanteSerializer(serializers.ModelSerializer):
    productoId = serializers.IntegerField(source="producto_id", allow_null=True)
    nombre = serializers.CharField(source="nombre_original")
    nombreNormalizado = serializers.CharField(source="nombre_normalizado")
    tipoNombre = serializers.CharField(source="get_tipo_display")
    proveedorId = serializers.IntegerField(source="proveedor_id", allow_null=True)
    proveedorNombre = serializers.SerializerMethodField()
    registradoPor = serializers.SerializerMethodField()
    resueltoPor = serializers.SerializerMethodField()
    resueltoEn = serializers.DateTimeField(source="resuelto_en")

    class Meta:
        model = Faltante
        fields = [
            "id",
            "productoId",
            "nombre",
            "nombreNormalizado",
            "cantidad",
            "fecha",
            "tipo",
            "tipoNombre",
            "proveedorId",
            "proveedorNombre",
            "estado",
            "registradoPor",
            "resueltoPor",
            "resueltoEn",
        ]

    def get_proveedorNombre(self, faltante):
        return faltante.proveedor.nombre if faltante.proveedor_id else None

    def get_registradoPor(self, faltante):
        return faltante.registrado_por.username

    def get_resueltoPor(self, faltante):
        return faltante.resuelto_por.username if faltante.resuelto_por_id else None
