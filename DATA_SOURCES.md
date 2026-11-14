# 공개 자료 수집

`scripts/collect_sources.py`가 검토한 공개 URL 7개를 순차 수집합니다.
`uv run python scripts/collect_sources.py --sync-frontend`로 BE·FE JSON을 동기화합니다.
수집일은 Asia/Seoul 기준이며 `app/data/source-manifest.json`에 응답 해시·시각을 남깁니다.
HTTP 오류·리디렉션·필수 가격 파싱 실패 시 기존 스냅샷은 바꾸지 않습니다. 자동 스케줄은 설정하지 않았습니다.

- CDA Newtown/Ashfield/Redfern: 지역 시작 요금과 운영사 지역→CBD 예상 시간. 특정 방의 확정 가격·실시간 공실이 아닙니다.
- UKO Newtown/Surry Hills: 공고 호실의 시작 요금·공고 입주 가능일. 실제 계약 전 확인이 필요합니다.
- University of Sydney: 학생 월 생활비 범위의 식비·통신비 하한을 참고 예산에 사용합니다. 취업자 개인 견적이 아닙니다.
- Transport for NSW: 성인 Opal 주간 상한 × 52 ÷ 12. 실제 출퇴근 운임이 아니며 공항 역 이용료·지역 열차는 별도입니다.

확인되지 않은 보증금·선납 월세·이사비·경로는 null로 유지합니다. 비용 부분 합계에는 0을 더하지만
누락 항목에 반드시 표시하며, 통근 미확인 후보는 `commute_verified: false`로 반환합니다.
기존 공식 체크리스트는 큐레이션 자료이며 수집 시각을 임의로 최신 날짜로 바꾸지 않습니다.

Flatmates는 수집 시 429 응답 및 종료 공고 리디렉션이 확인되어 이번 스냅샷에서 제외했습니다.
로그인·차단 우회, 개인 연락처나 사진 수집은 하지 않습니다.
