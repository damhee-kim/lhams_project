// 이벤트 타입 → 한글 배지 라벨 (내부 필터/통계 키는 영문 유지, 화면 표기만 한글화)
export const EVENT_LABELS = {
  CREATED: '생성',
  MODIFIED: '수정',
  MOVED: '파일 교체',
  DELETED: '삭제',
  MALWARE_DETECTED: '악성코드 탐지',
}

// 비전문가용 문장형 서술 — "OOO님이 ~했습니다"의 서술어 부분
export const EVENT_VERB = {
  CREATED: '파일을 생성했습니다',
  MODIFIED: '파일을 수정했습니다',
  MOVED: '파일을 교체(이동)했습니다',
  DELETED: '파일을 삭제했습니다',
  MALWARE_DETECTED: '파일에서 악성코드가 탐지되어 자동으로 격리했습니다',
}
