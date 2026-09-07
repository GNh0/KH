---
name: artifact-checks
description: Check requested deliverables for content, file structure, and readable rendered output when several formats or a separate artifact audit are involved.
---

# Artifact checks

사용자가 요청한 파일 형식·저장 위치·내용과 최종 산출물을 대조한다. 문서·시트·슬라이드·PDF 생성과 렌더링에는 현재 제공된 전용 스킬/도구를 사용한다.

파일 구조 검사만 필요하면 `python <plugin-root>/scripts/kh_check.py artifact <absolute-file>`을 사용할 수 있다. ZIP/XML/header 검사는 내용과 렌더링 성공을 보증하지 않는다. renderer가 없으면 구조 확인까지만 수행했다고 표시한다.

표·수식·그룹·보고서 H/D/F 밴드·페이지·한글 가독성 등 해당 형식의 실제 결과를 확인한다. 요구 대응표가 도움이 될 때만 작성하고 정해진 목차나 여러 별도 상태 파일을 강제하지 않는다.
