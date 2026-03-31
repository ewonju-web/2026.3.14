# -*- coding: utf-8 -*-
"""
인덱스 목록: 기종 탭별로 DB 오분류가 있어도 목록이 섞여 보이지 않게 보정.

- 지게차·덤프·로더: 굴삭기(EXC_*·모델 패턴)로 보이는 행 제외
- 굴삭기·지게차 등(어태치 제외): 채버켓 등 어태치먼트로 보이는 행 제외 → 어태치먼트 탭에서만 보이게
"""
from django.db.models import Q

# 두산 DX / 볼보 EC / 현대 HX / MX / S55V류 / 키워드 (management commands와 맞춤)
_EXC_MODEL_IREGEX = (
    r"(DX\d|EC\d|HX\d|MX\d|S\d{2,3}V|회링|코집|집게|굴삭|미니굴|엑스카)"
)


def _q_looks_like_excavator_row():
    exc_code = Q(sub_type__startswith="EXC_") | Q(weight_class__startswith="EXC_")
    model_pat = Q(model_name__iregex=_EXC_MODEL_IREGEX)
    return exc_code | model_pat


def _q_looks_like_attachment_item():
    """버킷·채버 등 어태치먼트로 분류하는 게 맞는 모델명(필요 시 키워드 추가)."""
    return Q(model_name__icontains="채버켓")


def exclude_excavator_misclassified_for_non_excavator_tabs(qs, filter_category: str):
    """지게차·덤프·로더 탭에서 굴삭기로 오인될 수 있는 행 제외."""
    if filter_category not in ("forklift", "dump", "loader"):
        return qs
    return qs.exclude(_q_looks_like_excavator_row())


def exclude_attachment_like_from_non_attachment_tabs(qs, filter_category: str):
    """
    어태치먼트가 아닌 기종 탭에서, 어태치로 보이는 매물 제외.
    filter_category가 비어 있으면(전체 등) 그대로 둔다.
    """
    valid = ("excavator", "forklift", "dump", "loader", "crane", "attachment", "other")
    if not filter_category or filter_category not in valid or filter_category == "attachment":
        return qs
    return qs.exclude(_q_looks_like_attachment_item())


def filter_attachment_tab(qs):
    """
    어태치먼트 탭: equipment_type=attachment 이거나,
    다른 타입으로 저장됐지만 모델명이 어태치(채버켓 등)로 보이는 매물 포함.
    """
    q = Q(equipment_type="attachment") | (
        Q(
            equipment_type__in=(
                "excavator",
                "forklift",
                "dump",
                "loader",
                "crane",
                "other",
            )
        )
        & _q_looks_like_attachment_item()
    )
    return qs.filter(q)
