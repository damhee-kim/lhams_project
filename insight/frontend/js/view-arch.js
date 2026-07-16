/* ===== 시스템 아키텍처 (SCR-05, 정적 도해) =====
 * 골격 마크업(SVG 포함, 런타임 값 없음)은 views/arch.jsp에 있다 — renderView()가 로드·주입한다. */
views.arch = async () => {
  await renderView('arch');
};
