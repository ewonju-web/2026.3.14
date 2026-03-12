import django_filters
from django.db.models import Q
from .models import Equipment


class EquipmentFilter(django_filters.FilterSet):
    # 🔹 기존 필터
    category = django_filters.CharFilter(field_name="category", lookup_expr="exact")
    op_type = django_filters.CharFilter(field_name="op_type", lookup_expr="exact")
    ton_cat = django_filters.CharFilter(field_name="tonnage_category", lookup_expr="exact")

    # 🔹 연식 / 가격 / 가동시간 범위 검색 (요청하신 부분)
    min_year = django_filters.NumberFilter(
        field_name="year_manufactured",
        lookup_expr="gte"
    )
    max_year = django_filters.NumberFilter(
        field_name="year_manufactured",
        lookup_expr="lte"
    )

    min_price = django_filters.NumberFilter(
        field_name="listing_price",
        lookup_expr="gte"
    )
    max_price = django_filters.NumberFilter(
        field_name="listing_price",
        lookup_expr="lte"
    )

    max_hours = django_filters.NumberFilter(
        field_name="hours_used",
        lookup_expr="lte"
    )

    # 🔹 통합 검색 (제목 / 제조사 / 모델명 / 지역)
    q = django_filters.CharFilter(method="filter_q")

    def filter_q(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(title__icontains=value) |
            Q(manufacturer__icontains=value) |
            Q(model_name__icontains=value) |
            Q(current_location__icontains=value)
        )

    class Meta:
        model = Equipment
        fields = [
            "category",
            "op_type",
            "ton_cat",
            "min_year",
            "max_year",
            "min_price",
            "max_price",
            "max_hours",
            "q",
        ]



