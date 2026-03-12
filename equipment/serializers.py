from rest_framework import serializers
from .models import Equipment


class EquipmentListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            "id",
            "title",
            "tonnage_precise",
            "op_type",
            "year_manufactured",
            "hours_used",
            "listing_price",
            "current_location",
            "manufacturer",
            "model_name",
            "tonnage_category",
        ]

    def get_title(self, obj):
        return f"{obj.manufacturer} {obj.tonnage_precise}톤 {obj.get_op_type_display()} {obj.model_name}"


class EquipmentListResponseSerializer(serializers.Serializer):
    summary = serializers.DictField()
    results = EquipmentListSerializer(many=True)

