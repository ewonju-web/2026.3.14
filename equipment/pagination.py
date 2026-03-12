from rest_framework.pagination import PageNumberPagination

class EquipmentPagination(PageNumberPagination):
    page_size = 20                 # 기본 20개
    page_size_query_param = "page_size"  # ?page_size=50
    max_page_size = 100            # 최대 100개까지만 허용


