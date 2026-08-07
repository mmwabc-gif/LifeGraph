from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_three_level_full_range_view_markup_is_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    for view in ("life", "year", "month"):
        assert f'data-life-view="{view}"' in html

    assert 'data-life-view="day"' not in html
    assert 'id="lifeMapDayView"' not in html
    assert 'id="dayGrid"' not in html

    for element_id in (
        "lifeMapLifeView",
        "lifeMapYearView",
        "lifeMapMonthView",
        "yearGrid",
        "monthGrid",
        "periodNavigator",
        "periodChildGrid",
        "periodDrawerBreadcrumb",
    ):
        assert f'id="{element_id}"' in html

    assert html.count('class="hierarchy-stage"') == 2
    assert "整个目标人生范围内的所有月份" in html


def test_hierarchy_logic_keeps_life_canvas_and_full_range_months() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'const frontendBuildVersion = "0.0.5"' in javascript
    assert 'switchLifeMapView("day")' not in javascript
    assert 'while (monthStart < bounds.target)' in javascript
    assert 'monthStart = monthEnd' in javascript
    assert 'openDateDrawer(resolved.isoDate)' in javascript
    assert 'openPeriodDrawer("year", String(year))' in javascript
    assert 'openPeriodDrawer("month", periodKey)' in javascript
    assert 'drawLifeGrid(currentProgress, force)' in javascript


def test_year_and_month_views_share_fixed_life_map_region() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '.hierarchy-stage {' in css
    assert 'min-width: 780px' in css
    assert 'height: 430px' in css
    assert '--hierarchy-cell-size: 44px' in css
    assert '--hierarchy-cell-size: 14px' in css
    assert 'overflow-y: hidden' in css


def test_compact_cells_keep_hover_and_content_markers() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'id="hierarchyPointerTooltip"' in html
    assert 'showHierarchyPointerTooltip(event, resolvedHoverText)' in javascript
    assert 'cell.addEventListener("mousemove", (event) => positionHierarchyPointerTooltip(event))' in javascript
    assert 'cell.title = hoverText || fullAriaLabel' not in javascript
    assert 'appendHierarchyMarkers(cell, state)' in javascript
    assert 'yearContentStatus[String(year)]' in javascript
    assert 'monthContentStatus[periodKey]' in javascript


def test_period_drawer_supports_year_month_and_day_content() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'async function openPeriodDrawer(scope, periodKey)' in javascript
    assert 'time_scope: selectedScope' in javascript
    assert 'period_key: selectedPeriodKey' in javascript
    assert 'periodNavigatorTitle' not in javascript
    assert 'id="periodNavigatorTitle"' not in (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert '.period-child-grid {' in css
    assert '.period-navigator[data-scope="year"] .period-child-grid' in css


def test_view_tab_order_is_life_month_year() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    assert '<h2 id="lifeMapViewTitle">太阳每天都是新的</h2>' in html
    assert 'data-life-view="life" aria-selected="true">日</button>' in html

    life_pos = html.index('data-life-view="life"')
    month_pos = html.index('data-life-view="month"')
    year_pos = html.index('data-life-view="year"')
    assert life_pos < month_pos < year_pos


def test_locator_buttons_are_removed_and_legend_shares_description_row() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'class="life-map-context-row"' not in html
    assert 'id="lifeMapBreadcrumb"' not in html
    assert 'id="hierarchyHoverStatus"' not in html
    assert 'id="hierarchyHoverBadge"' not in html
    assert 'id="lifeMapNavigation"' not in html
    assert 'id="lifeMapToday"' not in html
    assert 'id="lifeMapPrev"' not in html
    assert 'id="lifeMapNext"' not in html
    assert 'class="life-map-description-row"' in html
    assert 'class="legend life-map-legend-items"' in html
    assert '.life-map-description-row {' in css
    assert 'configureHierarchyNavigation' not in javascript
    assert '.hierarchy-pointer-tooltip {' in css


def test_year_and_month_hover_uses_pointer_following_tooltip() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="hierarchyPointerTooltip"' in html
    assert 'id="hierarchyPointerTitle"' in html
    assert 'id="hierarchyPointerMeta"' in html
    assert 'function showHierarchyPointerTooltip(event, text)' in javascript
    assert 'function positionHierarchyPointerTooltip(event)' in javascript
    assert 'activeLifeMapView === "life"' in javascript
    assert 'cell.addEventListener("mouseenter", (event) => showHierarchyPointerTooltip(event, resolvedHoverText))' in javascript
    assert 'cell.title = hoverText || fullAriaLabel' not in javascript
    assert 'hierarchyPointerTitle.textContent = parts.shift() || "—";' in javascript
    assert 'width: 244px;' in css
    assert 'border-radius: 16px;' in css
    assert 'background: rgba(251,250,246,.97);' in css
    assert 'const tooltip = hierarchyHoverBadge;' not in javascript
    assert 'setLifeMapBreadcrumb(' not in javascript



def test_month_drawer_uses_monday_first_week_grid() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="periodWeekdayHeader"' in html
    assert '<span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>' in html
    assert 'const mondayOffset = (firstDay.getUTCDay() + 6) % 7;' in javascript
    assert 'appendMonthCalendarCells(monthKey, selectedKey);' in javascript
    assert 'period-day-placeholder' in javascript
    assert 'grid-template-columns: repeat(7, minmax(0, 1fr));' in css
    assert '.period-weekday-header {' in css
    assert '.period-child-cell.is-outside-life' in css


def test_day_drawer_shows_only_selected_week() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'function weekChildrenForDay(dayKey)' in javascript
    assert 'const weekStart = addUtcDays(selected, -mondayOffset);' in javascript
    assert 'for (let index = 0; index < 7; index += 1)' in javascript
    assert 'function appendSelectedWeekCells(dayKey, selectedKey)' in javascript
    assert 'periodNavigatorTitle' not in javascript
    assert 'appendSelectedWeekCells(detail.period_key, selectedKey);' in javascript
    assert 'if (detail.scope === "month")' in javascript
    assert 'appendMonthCalendarCells(monthKey, selectedKey);' in javascript


def test_period_navigator_has_no_middle_instruction_heading() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="periodNavigatorTitle"' not in html
    assert "选择本周中的日期" not in html
    assert "选择本月中的日期" not in html
    assert "选择这一年中的月份" not in html
    assert "periodNavigatorTitle" not in javascript
    assert ".period-navigator-title" not in css


def test_period_drawer_header_has_centered_path_and_year_buttons() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "继续细分时间" not in html
    assert 'id="periodNavigatorHint"' not in html
    assert 'id="periodPreviousYear"' in html
    assert 'id="periodNextYear"' in html
    assert 'class="period-year-navigation"' in html
    assert 'function shiftPeriodKeyByYears(scope, periodKey, yearDelta)' in javascript
    assert 'function configurePeriodYearNavigation(scope, periodKey)' in javascript
    assert 'openPeriodDrawer(selectedScope, periodPreviousYear.dataset.periodKey)' in javascript
    assert 'openPeriodDrawer(selectedScope, periodNextYear.dataset.periodKey)' in javascript
    assert 'grid-template-columns: minmax(86px, 1fr) auto minmax(86px, 1fr);' in css
    assert 'justify-content: center;' in css


def test_drawer_day_labels_do_not_use_leading_zeroes() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'label: String(day),' in javascript
    assert 'label: String(value.getUTCDate()),' in javascript
    assert 'label: String(day).padStart(2, "0")' not in javascript
    assert 'label: String(value.getUTCDate()).padStart(2, "0")' not in javascript


def test_metric_cards_use_embedded_progress_bars() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'lifeDayMetric.style.setProperty("--metric-progress"' in javascript
    assert 'yearPercentMetric.style.setProperty("--metric-progress"' in javascript
    assert 'monthPercentMetric.style.setProperty("--metric-progress"' in javascript
    assert '.metric-card strong {' in css
    assert 'var(--metric-progress)' in css
    assert 'font-size: clamp(1.65rem, 3.15vw, 2.35rem);' in css


def test_period_picker_cells_are_compact() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'height: 30px;' in css
    assert 'height: 34px;' in css
    assert '.period-navigator {' in css
    assert 'padding: 14px;' in css


def test_life_canvas_does_not_create_horizontal_scrollbar() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'const measuredWidth = Math.floor(wrap.clientWidth || 0);' in javascript
    assert 'const cssWidth = measuredWidth > 0 ? measuredWidth : 780;' in javascript
    assert 'const cssWidth = Math.max(780' not in javascript
    assert '/* LifeGraph v0.0.2.19：人生视图 Canvas 自适应宽度，移除横向滚动条 */' in css
    assert 'overflow-x: hidden;' in css
    assert '#lifeCanvas {' in css
    assert 'min-width: 0;' in css
    assert 'max-width: 100%;' in css


def test_metric_cards_merge_labels_into_notes_below_progress() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '<span>步履不停</span>' not in html
    assert 'id="yearMetricTitle"' not in html
    assert 'id="monthMetricTitle"' not in html
    assert 'id="yearRemaining"' not in html
    assert 'id="monthRemaining"' not in html
    assert '步履不停，慢慢走，沿途皆是风景。' in html
    assert 'id="yearMetricNote"' in html
    assert 'id="monthMetricNote"' in html
    assert '途径${currentYear}，不赶时间，去吹吹风，年度结余${progress.year.remaining_days}天。' in javascript
    assert '${currentMonth}月小憩，看一看，走走停停，本月还有${progress.month.remaining_days}天。' in javascript
    assert '/* LifeGraph v0.0.2.23：进度卡移除抬头行，合并行程文案 */' in css
    assert 'grid-template-rows: auto auto;' in css
    assert '.metric-card > .metric-note {' in css
    assert '/* LifeGraph v0.0.2.24：进度卡下方文案统一居中 */' in css
    assert 'text-align: center;' in css


def test_content_cards_support_encrypted_editing_flow() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'async function startContentEdit(kind, item)' in javascript
    assert 'editButton.textContent = "编辑";' in javascript
    assert 'config.form.dataset.editId = item.id;' in javascript
    assert 'config.form.dataset.editRevision = String(item.revision);' in javascript
    assert 'config.form.querySelector(\'[name="title"]\').value = item.title || "";' in javascript
    assert 'method: editId ? "PUT" : "POST"' in javascript
    assert 'revision: editRevision' in javascript
    assert 'config.form.querySelector(\'button[type="submit"]\').textContent = "保存修改";' in javascript
    assert 'toggleContentForm("event", false)' in javascript
    assert 'toggleContentForm("memory", false)' in javascript
    assert 'toggleContentForm("plan", false)' in javascript
    assert 'requestAnimationFrame(() => captureContentFormSnapshot(kind));' in javascript
    assert '.content-edit-button {' in css
    assert '.event-form.is-editing,' in css


def test_content_cards_support_confirmed_soft_delete() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'const frontendBuildVersion = "0.0.5"' in javascript
    assert 'async function deleteScopedContent(kind, item, button)' in javascript
    assert 'const confirmed = await askConfirmation({' in javascript
    assert 'method: "DELETE"' in javascript
    assert 'body: JSON.stringify({ revision: item.revision })' in javascript
    assert 'content-delete-button' in javascript
    assert '.content-delete-button {' in css


def test_frontend_has_unified_recycle_bin_controls() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="trashButton"' in html
    assert 'id="trashDrawerContent"' in html
    assert 'id="emptyTrashButton"' in html
    assert 'id="trashList"' in html
    assert 'async function openTrashDrawer()' in javascript
    assert '/api/v1/trash/${encodeURIComponent(item.kind)}' in javascript
    assert 'body: JSON.stringify({ confirm: "EMPTY_TRASH" })' in javascript
    assert 'className = "trash-restore-button"' in javascript
    assert 'className = "trash-purge-button"' in javascript
    assert '.trash-card' in css
    assert '.trash-toolbar' in css


def test_full_page_continuous_day_grid_is_available() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="openFullPageView"' in html
    assert '>全页视图</button>' in html
    assert '<h2>太阳每一天都是新的</h2>' in html
    assert '>进入首页</button>' in html
    assert 'async function loadHome({ enterFullPage = false } = {})' in javascript
    assert 'if (enterFullPage) openFullPageLifeView();' in javascript
    assert 'await loadHome({ enterFullPage: true });' in javascript
    assert 'document.getElementById("refreshButton").addEventListener("click", () => loadHome());' in javascript
    assert 'id="fullPageLifeView"' in html
    assert 'id="fullPageLifeCanvas"' in html
    assert 'id="fullPageDateTooltip"' in html
    assert 'function drawFullPageLifeGrid(force = false)' in javascript
    assert 'function resolveFullPageDateFromPointer(event)' in javascript
    assert 'function scrollFullPageToDate(isoDate, behavior = "auto")' in javascript
    assert 'openDateDrawer(resolved.isoDate)' in javascript
    assert 'fullPageLifeCanvas.addEventListener("mousemove"' in javascript
    assert 'fullPageLifeCanvas.addEventListener("click"' in javascript
    assert 'document.documentElement.classList.add("full-page-life-open")' in javascript
    assert 'document.documentElement.classList.remove("full-page-life-open")' in javascript
    assert 'html.full-page-life-open' in css
    assert 'body.full-page-life-open' in css
    assert 'scrollbar-width: none' in css
    assert '.full-page-life-canvas-wrap::-webkit-scrollbar' in css
    assert '.full-page-life-view {' in css
    assert '.full-page-date-tooltip {' in css


def test_full_page_header_grows_on_narrow_viewports():
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    assert "flex: 0 0 auto;" in css
    assert "flex-shrink: 0;" in css
    assert "height: auto;" in css
    assert "grid-template-columns: repeat(2, minmax(0, 1fr));" in css
    assert "grid-column: 1 / -1;" in css


def test_home_uses_completed_day_count_consistently() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'id="lifeSentence"' in html
    assert 'document.getElementById("lifeSentence").textContent = `你已经走过 ${progress.life.elapsed_days.toLocaleString()} 天。`;' in javascript
    assert 'lifeDayMetric.textContent = progress.life.elapsed_days.toLocaleString();' in javascript
    assert 'lifeDayMetric.textContent = progress.life_day_number.toLocaleString();' not in javascript
    assert 'lifeMapViewTitle.textContent = "太阳每天都是新的";' in javascript
    assert '<h2 id="lifeMapViewTitle">太阳每天都是新的</h2>' in html


def test_home_hero_copy_and_life_ring_percentage_are_centered():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "LifeGraph v0.0.3.16：首页已走过天数说明字号协调" in stylesheet
    assert "LifeGraph v0.0.3.16：首页已走过天数说明字号协调" in stylesheet
    assert "font-size: clamp(.92rem, 1.55vw, 1.05rem);" in stylesheet
    assert ".life-percent {\n  display: grid;\n  place-items: center;" in stylesheet
    assert '<span>生命进度</span>' not in html



def test_profile_and_security_settings_ui_is_available() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="settingsButton"' in html
    assert 'id="fullPageSettingsButton"' in html
    assert 'id="settingsModal"' in html
    assert 'id="profileSettingsSummary"' in html
    assert 'id="profileDisplayNameValue"' in html
    assert 'id="profileBirthDateValue"' in html
    assert 'id="editProfileSettings"' in html
    assert 'id="profileSettingsForm"' in html
    assert 'id="changePinForm"' in html
    assert 'id="recoveryCredentialForm"' in html
    assert 'id="securitySlotSummary"' in html
    assert 'id="securityAuditList"' in html
    assert 'id="resetPinModal"' in html
    assert 'id="resetPinForm"' in html
    assert 'id="openResetPin"' in html
    assert 'api("/api/v1/profile/change-impact"' in javascript
    assert 'api("/api/v1/profile"' in javascript
    assert 'api("/api/v1/auth/change-pin"' in javascript
    assert 'api("/api/v1/auth/change-recovery"' in javascript
    assert 'api("/api/v1/security/summary"' in javascript
    assert 'api("/api/v1/auth/reset-pin"' in javascript
    assert '.settings-modal' in css
    assert 'z-index: 270' in css


def test_settings_modal_stays_inside_viewport_and_scrolls_its_content() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'class="settings-scroll-body"' in html
    assert "LifeGraph v0.0.4.3：个人设置限制在可视高度内，固定标题并隐藏式滚动内容" in stylesheet
    assert "display: flex;\n  flex-direction: column;\n  width: min(760px, 100%);" in stylesheet
    assert "max-height: calc(100vh - 40px);" in stylesheet
    assert "max-height: calc(100dvh - 40px);" in stylesheet
    assert "overflow: hidden;" in stylesheet
    assert ".settings-scroll-body {\n  min-height: 0;\n  overflow-y: auto;" in stylesheet
    assert ".settings-scroll-body::-webkit-scrollbar" in stylesheet
    assert "max-height: calc(100dvh - 20px);" in stylesheet
    assert ".settings-header {\n  flex: 0 0 auto;" in stylesheet
    assert "scrollbar-width: none;" in stylesheet


def test_settings_scroll_region_contains_all_long_form_sections() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")

    header_position = html.index('<header class="settings-header">', html.index('id="settingsModal"'))
    scroll_position = html.index('<div class="settings-scroll-body">')
    profile_position = html.index('id="profileSettingsForm"')
    security_position = html.index('id="changePinForm"')
    recovery_position = html.index('id="recoveryCredentialForm"')
    overview_position = html.index('id="securitySlotSummary"')
    backup_position = html.index('id="checkBackupButton"')
    restore_position = html.index('id="restoreImportBackupButton"')
    reset_modal_position = html.index('id="resetPinModal"')

    assert header_position < scroll_position
    assert scroll_position < profile_position < security_position < recovery_position < overview_position < backup_position < restore_position
    assert restore_position < reset_modal_position


def test_settings_groups_are_visually_separated_and_profile_starts_read_only() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert html.count('class="settings-group ') == 3
    assert 'id="profileSettingsGroupTitle">个人档案</h3>' in html
    assert 'id="securitySettingsGroupTitle">安全设置</h3>' in html
    assert 'id="backupSettingsGroupTitle">备份与迁移</h3>' in html
    assert '<h4>修改恢复密钥</h4>' in html
    assert 'class="settings-group-icon"' in html
    assert 'id="profileSettingsSummary" class="profile-settings-summary"' in html
    assert 'id="profileSettingsForm" class="form-grid compact-form profile-settings-form hidden"' in html
    assert 'function setProfileSettingsEditMode(editing, { focus = true } = {})' in javascript
    assert 'setProfileSettingsEditMode(false, { focus: false });' in javascript
    assert 'editProfileSettingsButton?.addEventListener("click", () => setProfileSettingsEditMode(true));' in javascript
    assert 'cancelProfileSettingsButton?.addEventListener("click", () => setProfileSettingsEditMode(false));' in javascript
    assert 'LifeGraph v0.0.4：个人设置分区重构、恢复密钥归位与档案默认只读' in stylesheet
    assert '.settings-group-header {' in stylesheet
    assert '.profile-summary-list {' in stylesheet


def test_quick_memory_entry_is_available_on_home_and_full_page() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="quickMemoryHomeButton"' in html
    assert 'id="quickMemoryFullPageButton"' in html
    assert html.count('>记一记</button>') >= 2
    assert 'id="quickMemoryModal"' in html
    assert 'id="quickMemoryForm"' in html
    assert 'id="quickMemoryDateText"' in html
    assert '今天想记什么' in html
    assert 'quickMemoryHomeButton?.addEventListener("click", openQuickMemoryModal);' in javascript
    assert 'quickMemoryFullPageButton?.addEventListener("click", openQuickMemoryModal);' in javascript
    assert 'async function saveQuickMemory(event)' in javascript
    assert 'time_scope: "day"' in javascript
    assert 'period_key: currentProgress.today' in javascript
    assert 'api("/api/v1/memories"' in javascript
    assert 'deriveQuickMemoryTitle(content)' in javascript
    assert 'isQuickMemoryDirty()' in javascript
    assert '今日记忆已加密保存' in javascript
    assert 'LifeGraph v0.0.5.4.2：记一记快捷入口与今日记忆二级窗口' in stylesheet
    assert '.quick-memory-modal {' in stylesheet
    assert '.quick-memory-entry-button {' in stylesheet


def test_auto_backup_settings_and_history_ui_is_available() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "autoBackupForm",
        "saveAutoBackupButton",
        "runAutoBackupButton",
        "autoBackupStatusText",
        "autoBackupHistorySummary",
        "autoBackupHistoryList",
        "refreshAutoBackupHistoryButton",
        "clearAutoBackupHistoryButton",
    ):
        assert f'id="{element_id}"' in html
    assert 'async function loadAutoBackupPanel()' in javascript
    assert 'api("/api/v1/backup/auto"' in javascript
    assert 'api("/api/v1/backup/auto/run"' in javascript
    assert 'api("/api/v1/backup/auto/history/clear"' in javascript
    assert 'downloadAutoBackup(item, downloadButton)' in javascript
    assert 'deleteAutoBackupHistoryItem(item, deleteButton)' in javascript
    assert "LifeGraph v0.0.4.4：本地自动备份与备份历史管理" in stylesheet
    assert '.auto-backup-history-item {' in stylesheet


def test_recovery_rotation_and_security_summary_ui_is_available() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "recoveryCredentialForm",
        "customRecoveryFields",
        "refreshSecuritySummaryButton",
        "securitySlotSummary",
        "securityAuditSummary",
        "securityAuditList",
        "recoveryDescription",
    ):
        assert f'id="{element_id}"' in html
    assert 'function syncRecoveryCredentialMode()' in javascript
    assert 'async function loadSecuritySummary()' in javascript
    assert 'function renderSecuritySummary(summary)' in javascript
    assert 'showRecoverySecret(result.generated_recovery_secret' in javascript
    assert 'recoveryCredentialForm?.addEventListener("submit"' in javascript
    assert "LifeGraph v0.0.4.5：恢复凭据轮换、密钥槽信息与安全审计摘要" in stylesheet
    assert '.security-slot-summary {' in stylesheet
    assert '.security-audit-item {' in stylesheet
    assert '#recoveryModal {' in stylesheet
    assert 'z-index: 330;' in stylesheet


def test_date_drawer_fullscreen_expand_ui_is_available() -> None:
    html = (PROJECT_ROOT / "frontend/index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend/app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend/styles.css").read_text(encoding="utf-8")

    assert 'id="expandDateDrawer"' in html
    assert 'aria-label="展开日期详情"' in html
    assert 'const expandDateDrawerButton = document.getElementById("expandDateDrawer");' in javascript
    assert 'function setDateDrawerExpanded(expanded)' in javascript
    assert 'dateDrawer.classList.toggle("is-expanded", dateDrawerExpanded);' in javascript
    assert 'expandDateDrawerButton?.addEventListener("click", toggleDateDrawerExpanded);' in javascript
    assert '.date-drawer.is-expanded {' in stylesheet


def test_drawer_navigation_uses_keyboard_arrows_instead_of_wheel() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'handleDrawerKeyboardNavigation' in javascript
    assert 'event.key === "ArrowLeft"' in javascript
    assert 'event.key === "ArrowRight"' in javascript
    assert 'addEventListener("wheel"' not in javascript
    assert 'handleDrawerContentWheel' not in javascript
    assert 'drawerScrollHint' not in javascript
    assert 'drawer-scroll-hint' not in css
    assert 'drawerScrollHint' not in html


def test_alt_enter_opens_current_drawer_context() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'async function handleDrawerOpenShortcut(event)' in javascript
    assert 'event.key !== "Enter" || !event.altKey' in javascript
    assert 'function drawerShortcutTarget()' in javascript
    assert 'fullPageViewportAnchorDate() || selectedDate || navigatorDate || currentProgress.today' in javascript
    assert 'activeLifeMapView === "year"' in javascript
    assert 'activeLifeMapView === "month"' in javascript
    assert 'await openPeriodDrawer(target.scope, target.periodKey)' in javascript
    assert 'if (await handleDrawerOpenShortcut(event)) return;' in javascript


def test_memory_rich_text_editor_ui_is_wired() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    stylesheet = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '<script src="/static/tinymce/tinymce.min.js"></script>' in html
    assert 'id="quickMemoryContent"' in html
    assert 'id="memoryContent"' in html
    assert 'function initMemoryRichEditor(editorId, initialHtml = "")' in javascript
    assert 'base_url: "/static/tinymce"' in javascript
    assert 'license_key: "gpl"' in javascript
    assert 'content_format: "html"' in javascript
    assert 'sanitizeRichMemoryHtml(item.content)' in javascript
    assert 'memory-rich-content' in javascript
    assert 'v0.0.5.4.2 TinyMCE memory rich text' in stylesheet
    assert '.memory-rich-content {' in stylesheet
