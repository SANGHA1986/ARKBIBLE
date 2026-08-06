/** 백엔드 API 주소
 * - 로컬: http://127.0.0.1:8000 (또는 8001)
 * - Render: 환경변수 NEXT_PUBLIC_API_URL
 */
export const API =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://127.0.0.1:8000";
