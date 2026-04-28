import os
import time

import pandas as pd
import requests

# 환경변수 우선, 없으면 기본 키 사용
API_KEY = os.getenv("KAKAO_REST_API_KEY", "94b05a24389cc92ad3ea84fe4be92173")

keywords = [
    "굴삭기 부품",
    "굴삭기 수리",
    "굴삭기 AS",
    "중장비 부품",
    "중장비 수리",
    "건설기계 정비",
    "굴삭기 정비",
    "포크레인 부품",
    "포크레인 수리",
    "덤프트럭 부품",
    "덤프트럭 수리",
    "덤프트럭 정비",
    "지게차 부품",
    "지게차 수리",
    "지게차 정비",
    "크레인 부품",
    "크레인 수리",
    "크레인 정비",
    "스키로더 수리",
    "로더 정비",
]

regions = [
    "서울",
    "경기",
    "인천",
    "부산",
    "대구",
    "광주",
    "대전",
    "울산",
    "세종",
    "강원",
    "충북",
    "충남",
    "전북",
    "전남",
    "경북",
    "경남",
    "제주",
]


def main():
    if not API_KEY:
        raise RuntimeError("KAKAO_REST_API_KEY가 비어 있습니다.")

    results = []
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {API_KEY}"}

    for region in regions:
        for keyword in keywords:
            for page in range(1, 4):
                params = {"query": f"{region} {keyword}", "size": 15, "page": page}
                res = requests.get(url, headers=headers, params=params, timeout=10)
                res.raise_for_status()
                payload = res.json()
                docs = payload.get("documents", [])
                if not docs:
                    break

                for d in docs:
                    results.append(
                        {
                            "업체명": d.get("place_name", ""),
                            "전화번호": d.get("phone", ""),
                            "주소": d.get("road_address_name") or d.get("address_name", ""),
                            "위도": d.get("y", ""),
                            "경도": d.get("x", ""),
                            "지역": region,
                            "키워드": keyword,
                        }
                    )
                time.sleep(0.3)
            print(f"✅ {region} - {keyword}")

    df = pd.DataFrame(results)
    df.drop_duplicates(subset=["업체명", "전화번호"], inplace=True)
    df.to_csv("전국_중장비업체.csv", index=False, encoding="utf-8-sig")
    print(f"\n총 {len(df)}개 업체 수집 완료!")


if __name__ == "__main__":
    main()
