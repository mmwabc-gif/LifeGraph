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

    assert 'const frontendBuildVersion = "0.0.10"' in javascript
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

    assert '<h2 id="lifeMapViewTitle">月视图</h2>' in html
    assert 'data-life-view="life" aria-selected="false">日</button>' in html
    assert 'data-life-view="month" aria-selected="true">月</button>' in html

    life_pos = html.index('data-life-view="life"')
    month_pos = html.index('data-life-view="month"')
    year_pos = html.index('data-life-view="year"')
    assert life_pos < month_pos < year_pos

    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert 'let activeLifeMapView = "month";' in javascript
    assert 'activeLifeMapView = "month";' in javascript


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

    assert 'const frontendBuildVersion = "0.0.10"' in javascript
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
    assert 'async function loadHome()' in javascript
    assert 'if (enterFullPage) openFullPageLifeView();' not in javascript
    assert 'await loadHome({ enterFullPage: true });' not in javascript
    assert 'await loadHome();' in javascript
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
    assert '<h2 id="lifeMapViewTitle">月视图</h2>' in html


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

    assert html.count('class="settings-group ') == 4
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
    assert 'api("/api/v1/backup/auto/reminder"' in javascript
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
    assert 'dateDrawer.addEventListener("wheel"' not in javascript
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


def test_memory_map_tag_filter_controls_and_highlight_hooks_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "memoryMapFilterHomeButton",
        "memoryMapFilterFullPageButton",
        "memoryMapFilterModal",
        "memoryMapFilterForm",
        "memoryMapFilterTagOptions",
        "memoryMapFilterSummary",
    ):
        assert f'id="{element_id}"' in html

    assert 'async function refreshMemoryMapTagMatches' in javascript
    assert '/api/v1/content/tag-map?' in javascript
    assert 'memoryMapScopeMatches("day", dateKey)' in javascript
    assert 'memoryMapScopeMatches("month", periodKey)' in javascript
    assert 'memoryMapScopeMatches("year", String(year))' in javascript
    assert '.hierarchy-cell.is-tag-filter-muted' in css
    assert '.hierarchy-cell.is-tag-filter-match' in css
    assert '事件、记忆或计划所在时间范围' in html
    assert 'memoryMapTagMatches.contentCount' in javascript


def test_memory_map_filter_event_binding_uses_defined_handler():
    app_js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "async function openMemoryMapFilterModal()" in app_js
    assert 'addEventListener("click", openMemoryMapFilterModal)' in app_js
    assert "openMemoryMapTagFilterModal" not in app_js


def test_tag_management_settings_ui_and_handlers_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "tagSettingsGroupTitle",
        "tagManagementSummary",
        "tagManagementNewName",
        "createManagedTag",
        "tagManagementList",
    ):
        assert f'id="{element_id}"' in html

    assert 'async function createManagedTag()' in javascript
    assert 'function renderTagManagement()' in javascript
    assert 'function renderTagManagementEditRow(row, tag)' in javascript
    assert 'async function deleteManagedTag(tag)' in javascript
    assert 'method: "PUT"' in javascript
    assert 'method: "DELETE"' in javascript
    assert '.tag-management-list {' in css
    assert '.tag-management-row {' in css
    assert 'const frontendBuildVersion = "0.0.10";' in javascript
    assert '/assets/app.js?v=0.0.10' in html


def test_unified_content_center_ui_and_handlers_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "contentCenterHomeButton",
        "contentCenterFullPageButton",
        "contentCenterModal",
        "contentCenterForm",
        "contentCenterQuery",
        "contentCenterDateFrom",
        "contentCenterDateTo",
        "contentCenterSort",
        "contentCenterTagOptions",
        "contentCenterResults",
        "contentCenterSummary",
    ):
        assert f'id="{element_id}"' in html

    assert "async function openContentCenterModal()" in javascript
    assert "async function runContentCenterBrowse()" in javascript
    assert "/api/v1/content/search?" in javascript
    assert "selectedContentCenterTagIds.forEach" in javascript
    assert "function renderContentCenterTagOptions()" in javascript
    assert "focusContentCenterTarget(item.kind, item.id)" in javascript
    assert 'addEventListener("click", openContentCenterModal)' in javascript
    assert ".content-center-card {" in css
    assert ".content-center-result-card {" in css
    assert ".content-center-tag-chip {" in css


def test_unified_search_ui_and_handlers_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '<h2 id="memorySearchTitle">统一搜索</h2>' in html
    for value in ("event", "memory", "plan"):
        assert f'name="search_kind" value="{value}" checked' in html
    assert "function selectedMemorySearchKinds()" in javascript
    assert "/api/v1/content/search?" in javascript
    assert "focusMemorySearchTarget(item.kind, item.id)" in javascript
    assert "memory-search-kind-badge" in javascript
    assert ".memory-search-kind-options {" in css
    assert ".memory-search-kind-badge.is-event" in css


def test_event_and_plan_forms_share_unified_tag_controls() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (root / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (root / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "toggleEventTagPicker",
        "eventSelectedTags",
        "eventTagPicker",
        "eventTagOptions",
        "eventNewTagName",
        "toggleMemoryTagPicker",
        "memorySelectedTags",
        "memoryTagPicker",
        "memoryTagOptions",
        "memoryNewTagName",
        "togglePlanTagPicker",
        "planSelectedTags",
        "planTagPicker",
        "planTagOptions",
        "planNewTagName",
    ):
        assert f'id="{element_id}"' in html

    for removed_button_id in ("createEventTag", "createMemoryTag", "createPlanTag"):
        assert f'id="{removed_button_id}"' not in html
    assert html.count('class="memory-tag-inline-create-input"') == 3
    assert html.count('aria-label="输入新标签名称，按回车创建并选中"') == 3
    assert 'document.getElementById("eventNewTagName")?.addEventListener("keydown"' in javascript
    assert 'document.getElementById("memoryNewTagName")?.addEventListener("keydown"' in javascript
    assert 'document.getElementById("planNewTagName")?.addEventListener("keydown"' in javascript
    assert 'showToast(`已选中标签 #${existing.name}`, "success")' in javascript
    assert 'showToast(`标签 #${tag.name} 已创建并选中`, "success")' in javascript
    assert ".memory-tag-inline-create-input {" in css
    assert "flex: 0 0 9.5em;" in css

    assert 'event: new Set()' in javascript
    assert 'plan: new Set()' in javascript
    assert 'function tagModeForKind(kind)' in javascript
    assert 'async function syncContentTags(kind, contentId, selectedIds)' in javascript
    assert '/api/v1/content/${encodeURIComponent(kind)}/${encodeURIComponent(contentId)}/tags' in javascript
    assert 'if (item.tags?.length) {' in javascript


def test_content_center_quick_tag_organizer_is_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="contentCenterTitle">浏览事件、记忆与计划</h2>' in html
    assert "async function openContentCenterQuickTagEditor(item, card, trigger, readonlyTags)" in javascript
    assert "function closeContentCenterQuickTagEditor" in javascript
    assert 'tagButton.textContent = "整理标签"' in javascript
    assert 'method: "PUT"' in javascript
    assert 'body: JSON.stringify({ tag_ids: [...draftIds] })' in javascript
    assert ".content-center-quick-tag-editor {" in css
    assert ".content-center-quick-tag-chip {" in css
    assert ".content-center-result-main {" in css


def test_content_center_quick_tag_hotfix_and_drawer_return_are_present() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'save.textContent = "保存标签"' in javascript
    assert 'save.disabled = true' in javascript
    assert 'function suspendContentCenterForDrawer(trigger = null)' in javascript
    assert 'function resumeContentCenterAfterDrawer()' in javascript
    assert 'contentCenterResults.scrollTop = resumeState.scrollTop || 0' in javascript
    assert 'resumeContentCenterAfterDrawer();' in javascript
    assert 'top.append(titleLead, topActions);' in javascript
    assert 'main.append(snippet);' in javascript
    assert 'card.append(top, main, readonlyTags);' in javascript
    assert '.content-center-quick-tag-heading-actions {' in css
    assert 'padding: 0 12px 10px;' in css


def test_content_center_results_keep_card_height_and_scroll_internally():
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    assert ".content-center-results {" in css
    assert "flex: 1 1 auto;" in css
    assert "overflow-y: auto;" in css
    assert "grid-auto-rows: max-content;" in css
    assert "align-content: start;" in css
    assert ".content-center-results > .content-center-result-card" in css


def test_content_center_bulk_tag_organizer_is_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "contentCenterBatchToolbar",
        "contentCenterSelectAll",
        "contentCenterSelectedCount",
        "contentCenterBulkTags",
        "contentCenterClearSelection",
        "contentCenterBatchTagEditor",
        "contentCenterBatchTagOptions",
        "contentCenterApplyBatchTags",
    ):
        assert f'id="{element_id}"' in html

    assert "const selectedContentCenterItems = new Map();" in javascript
    assert "async function openContentCenterBatchTagEditor()" in javascript
    assert "async function applyContentCenterBatchTags()" in javascript
    assert 'api("/api/v1/content/bulk/tags"' in javascript
    assert 'operation === "add"' in javascript
    assert 'data-content-center-select-key' in javascript
    assert ".content-center-batch-toolbar {" in css
    assert ".content-center-batch-tag-editor {" in css


def test_content_center_prioritizes_result_viewport_space() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "/* LifeGraph v0.0.7.7.1：内容中心空间利用优化 */" in css
    assert "height: min(96vh, 940px);" in css
    assert 'grid-template-areas:' in css
    assert '"quick"' in css
    assert '"filters"' in css
    assert '"tags"' in css
    assert "@media (max-height: 760px) and (min-width: 721px)" in css
    assert ".content-center-hint {\n    display: none;" in css



def test_content_center_quick_filter_row_keeps_kind_switches_beside_keyword() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    quick_row_start = index.index('<div class="content-center-quick-row">')
    quick_row_end = index.index('</div>\n          <div class="content-center-filter-grid">', quick_row_start)
    quick_row = index[quick_row_start:quick_row_end]

    assert 'id="contentCenterQuery"' in quick_row
    assert 'class="content-center-kinds"' in quick_row
    assert 'value="event"' in quick_row
    assert 'value="memory"' in quick_row
    assert 'value="plan"' in quick_row
    assert 'id="resetContentCenter"' not in quick_row
    assert '.content-center-quick-row {' in css
    assert '.content-center-kind-options {\n  flex-wrap: nowrap;' in css


def test_content_center_filter_labels_sit_before_controls_on_desktop() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for label in ("快速过滤", "日期", "-", "排序"):
        assert f'<span class="content-center-field-label">{label}</span>' in index

    assert 'class="content-center-hint"' not in index

    assert 'class="content-center-keyword content-center-inline-field"' in index
    assert index.count('class="content-center-inline-field"') >= 3
    assert "/* LifeGraph v0.0.7.7.3：内容中心筛选标签改为控件前置 */" in css
    assert ".content-center-inline-field {\n  display: flex;" in css
    assert ".content-center-field-label {" in css
    assert "white-space: nowrap;" in css


def test_content_center_batch_toolbar_sits_below_scrollable_results() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    results_pos = html.index('id="contentCenterResults"')
    editor_pos = html.index('id="contentCenterBatchTagEditor"')
    toolbar_pos = html.index('id="contentCenterBatchToolbar"')

    assert results_pos < editor_pos < toolbar_pos
    assert "/* LifeGraph v0.0.7.7.5：内容中心批量工具栏移至结果区底部 */" in css
    assert ".content-center-results-section > .content-center-batch-toolbar {" in css
    assert "margin: 0;" in css


def test_content_center_header_divider_and_batch_mode_entry() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "border-bottom: 1px solid rgba(49, 92, 77, .12);" in css
    assert 'id="contentCenterBatchModeToggle"' in html
    assert '>批量整理</button>' in html
    assert 'id="contentCenterBatchToolbar" class="content-center-batch-toolbar hidden"' in html
    assert "let contentCenterBatchMode = false;" in javascript
    assert "function setContentCenterBatchMode(enabled" in javascript
    assert 'contentCenterBatchModeToggle?.addEventListener("click", toggleContentCenterBatchMode);' in javascript
    assert 'contentCenterBatchModeToggle.textContent = contentCenterBatchMode ? "退出批量" : "批量整理";' in javascript
    assert "/* LifeGraph v0.0.7.7.7：内容中心批量整理按需进入 */" in css
    assert ".content-center-results-heading {\n  justify-content: flex-start;\n  text-align: left;" in css
    assert ".content-center-results-heading .content-center-batch-mode-toggle {\n  margin-left: auto;" in css
    assert ".content-center-modal:not(.is-batch-mode) .content-center-result-select {\n  display: none;" in css



def test_content_center_row_actions_move_into_title_line() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'titleLead.append(selectLabel, titleButton);' in javascript
    assert 'topActions.append(tagButton, scope);' in javascript
    assert 'top.append(titleLead, topActions);' in javascript
    assert 'card.append(top, main, readonlyTags);' in javascript
    assert 'openHint.textContent = "点击上方内容打开时间详情"' not in javascript
    assert 'rowActions.append(actionLead, tagButton);' not in javascript
    assert "/* LifeGraph v0.0.7.7.8：内容卡片标题行整合单条整理与批量选择 */" in css
    assert ".content-center-result-top-actions {" in css
    assert ".content-center-modal.is-batch-mode .content-center-quick-tag-toggle {\n  display: none;" in css
    assert ".content-center-result-actions,\n.content-center-result-action-lead,\n.content-center-open-hint {\n  display: none !important;" in css



def test_content_center_tag_filters_share_row_with_stacked_actions() -> None:
    index = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    row_start = index.index('<div class="content-center-tags-row">')
    row_end = index.index('</div>\n        </form>', row_start)
    row = index[row_start:row_end]

    assert 'class="content-center-tags"' in row
    assert 'id="contentCenterTagOptions"' in row
    assert 'class="content-center-actions content-center-tags-actions"' in row
    assert 'id="resetContentCenter"' in row
    assert '>应用整理</button>' in row
    assert row.index('id="contentCenterTagOptions"') < row.index('id="resetContentCenter"')
    assert "/* LifeGraph v0.0.7.7.9：标签筛选与整理操作左右分栏 */" in css
    assert "grid-template-columns: minmax(0, 1fr) 156px;" in css
    assert ".content-center-tags-actions {\n  display: flex;\n  flex-direction: column;" in css
    assert "/* LifeGraph v0.0.7.7.10：固定标签筛选与操作按钮同一网格行 */" in css
    assert ".content-center-tags-row > .content-center-tags-actions {\n  grid-area: auto;\n  grid-column: 2;\n  grid-row: 1;" in css


def test_content_cards_expose_encrypted_attachment_panel() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'attachmentButton.className = "content-attachment-button"' in javascript
    assert 'attachmentButton.textContent = `附件 ${Number.isInteger(item.attachment_count) ? item.attachment_count : 0}`' in javascript
    assert 'formData.append("attachment_file", file, file.name);' in javascript
    assert 'className = "attachment-panel hidden"' in javascript
    assert 'textContent = "＋ 添加附件"' in javascript
    assert '单个附件最多 50 MB' in javascript
    assert '/api/v1/attachments/${encodeURIComponent(attachment.id)}/download' in javascript
    assert 'article.appendChild(attachmentPanel);' in javascript
    assert 'button.textContent = `附件 ${attachments.length}`;' in javascript
    assert '/* LifeGraph v0.0.8.1：内容附件基础能力 */' in css
    assert '.attachment-panel {' in css
    assert '.attachment-item {' in css


def test_new_content_forms_support_pending_attachments_before_save() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for kind in ("event", "memory", "plan"):
        assert f'data-pending-attachments="{kind}"' in html
        assert f'id="{kind}PendingAttachments"' in html
        assert f'id="{kind}PendingAttachmentList"' in html
        assert f'document.getElementById("{kind}PendingAttachments")' in javascript

    assert 'const pendingContentAttachments = {' in javascript
    assert 'async function uploadPendingContentAttachments(kind, contentId)' in javascript
    assert 'const attachmentResult = await uploadPendingContentAttachments(kind, savedItem.id);' in javascript
    assert 'formNode.dataset.editId = savedItem.id;' in javascript
    assert 'clearPendingContentAttachments(kind);' in javascript
    assert '附件上传失败，可再次保存重试' in javascript
    assert '.content-form-attachment-field {' in css
    assert '.pending-attachment-list {' in css


def test_image_attachments_render_thumbnails_and_secure_preview_modal() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for element_id in (
        "attachmentPreviewModal",
        "attachmentPreviewTitle",
        "attachmentPreviewImage",
        "attachmentPreviewPrevious",
        "attachmentPreviewNext",
        "downloadAttachmentPreview",
        "closeAttachmentPreview",
    ):
        assert f'id="{element_id}"' in html

    assert 'function isImageAttachment(attachment)' in javascript
    assert 'async function fetchAttachmentBlob(attachment)' in javascript
    assert 'async function attachmentObjectUrl(attachment)' in javascript
    assert 'function createAttachmentThumbnail(attachment, images, imageIndex, { lazy = false } = {})' in javascript
    assert 'openAttachmentPreview(images, imageIndex, button);' in javascript
    assert 'navigateAttachmentPreview(event.key === "ArrowLeft" ? -1 : 1);' in javascript
    assert 'releaseAllAttachmentObjectUrls();' in javascript
    assert 'if (isImageFile(file)) {' in javascript
    assert '/* LifeGraph v0.0.8.2：图片附件缩略图与沉浸式预览 */' in css
    assert '.attachment-thumbnail-button {' in css
    assert '.attachment-preview-modal {' in css
    assert '.attachment-preview-image {' in css


def test_content_center_uses_inline_enter_to_create_tags() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="contentCenterBatchNewTagName" class="content-center-batch-tag-inline-input"' in html
    assert 'id="contentCenterBatchCreateTag"' not in html
    assert 'class="content-center-batch-create"' not in html
    assert 'input.className = "content-center-quick-tag-inline-input";' in javascript
    assert 'input.placeholder = "＋ 新标签";' in javascript
    assert 'createButton.textContent = "新建并选中";' not in javascript
    assert 'contentCenterBatchCreateTagButton' not in javascript
    assert 'createContentCenterBatchTag();' in javascript
    assert 'event.key !== "Enter"' in javascript
    assert '.content-center-quick-tag-inline-input,' in css
    assert '.content-center-batch-tag-inline-input {' in css


def test_attachment_preview_stage_cannot_cover_footer_actions() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '/* LifeGraph v0.0.8.2.1：图片预览底栏与内容中心行内标签新建修复 */' in css
    assert '.attachment-preview-stage,\n.attachment-preview-image-wrap {\n  overflow: hidden;' in css
    assert '.attachment-preview-image {\n  width: 100%;\n  height: 100%;' in css
    assert '.attachment-preview-footer {\n  position: relative;\n  z-index: 3;' in css


def test_attachment_preview_is_borderless_supports_wheel_and_middle_click_fullscreen() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'const attachmentPreviewStage = attachmentPreviewModal?.querySelector(".attachment-preview-stage");' in javascript
    assert 'attachmentPreviewStage?.addEventListener("wheel"' in javascript
    assert 'navigateAttachmentPreview(delta > 0 ? 1 : -1);' in javascript
    assert 'attachmentPreviewImage?.addEventListener("auxclick"' in javascript
    assert 'attachmentPreviewImage?.addEventListener("contextmenu"' in javascript
    assert 'closeAttachmentPreview();' in javascript
    assert 'event.button !== 1' in javascript
    assert 'toggleAttachmentPreviewFullscreen();' in javascript
    assert 'attachmentPreviewModal.requestFullscreen' in javascript
    assert 'document.exitFullscreen()' in javascript
    assert 'document.addEventListener("fullscreenchange"' in javascript
    assert '/* LifeGraph v0.0.8.2.3：默认中等尺寸预览，中键切换真正全屏 */' in css
    assert ".attachment-preview-shell {\n  position: relative;\n  display: block;\n  width: min(82vw, 1180px);\n  height: min(78dvh, 780px);" in css
    assert ".attachment-preview-modal.is-fullscreen-zoom .attachment-preview-shell" in css
    assert "width: 100vw;\n  height: 100dvh;" in css
    assert "border: 0;\n  border-radius: 14px;" in css
    assert ".attachment-preview-modal.is-fullscreen-zoom .attachment-preview-shell" in css
    assert "border-radius: 0;\n  box-shadow: none;" in css
    assert ".attachment-preview-header,\n.attachment-preview-footer {\n  position: absolute;" in css
    assert ".attachment-preview-nav {\n  position: absolute;" in css
    assert 'cursor: zoom-in;' in css
    assert 'cursor: zoom-out;' in css


def test_attachment_time_is_independent_and_shown_as_timeline_relationship() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'function attachmentTimelineLabel(attachment)' in javascript
    assert 'return `拍摄于 ${time}`;' in javascript
    assert 'return `文档创建于 ${time}`;' in javascript
    assert 'return `文件修改于 ${time}`;' in javascript
    assert 'return `来源内容日期 ${String(attachment.timeline_date || time).slice(0, 10)}`;' in javascript
    assert 'return `附件添加于 ${time}`;' in javascript
    assert 'fallbackButton.textContent = "归入来源/添加时间";' in javascript
    assert '/timeline-fallback`' in javascript
    assert 'timelineButton.textContent = `时间轴归属 ${attachment.timeline_date}`;' in javascript
    assert 'openPeriodDrawer("day", attachment.timeline_date)' in javascript
    assert 'formData.append("file_last_modified_ms", String(Math.trunc(file.lastModified)));' in javascript
    assert 'adoptButton.textContent = "采用";' not in javascript
    assert '建议挂接日期' not in javascript
    assert '/* LifeGraph v0.0.8.4：资料双重时间关系与时间轴归属 */' in css
    assert '.attachment-timeline-meta {' in css
    assert '.attachment-timeline-date-button {' in css


def test_period_drawer_has_material_section_for_file_own_timeline_date() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="materialSection"' in html
    assert 'id="materialList"' in html
    assert '按文件自身时间归属到人生时间轴' in html
    assert 'function renderMaterialList(materials = [], options = {})' in javascript
    assert 'renderMaterialList(detail.materials || [], {' in javascript
    assert 'sourceButton.textContent = `来自 ${source.period_key} · ${materialSourceKindLabel(source.kind)}：${source.title || "未命名内容"}`;' in javascript
    assert 'state.has_material' in javascript
    assert 'labels.push("有资料")' in javascript
    assert '.material-list {' in css
    assert '.hierarchy-material-marker {' in css
    assert '.period-material-marker {' in css



def test_material_center_entry_filters_and_relation_actions_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="materialCenterHomeButton"' in html
    assert 'id="materialCenterFullPageButton"' in html
    assert 'id="materialCenterModal"' in html
    assert 'id="materialCenterQuery"' in html
    assert 'name="material_category" value="image" checked' in html
    assert 'name="material_category" value="document" checked' in html
    assert 'name="material_category" value="other" checked' in html
    assert 'id="materialCenterDateFrom"' in html
    assert 'id="materialCenterDateTo"' in html
    assert 'id="materialCenterSort"' in html
    assert 'id="materialCenterTimelineView"' in html
    assert 'id="materialCenterListView"' in html
    assert '>时间轴</button>' in html
    assert '>列表</button>' in html
    assert 'class="material-center-mode-tabs" role="tablist"' in html
    assert 'class="material-center-mode-tab is-active"' in html

    assert 'async function openMaterialCenterModal()' in javascript
    assert 'async function runMaterialCenterBrowse()' in javascript
    assert '/api/v1/materials/browse?' in javascript
    assert 'function renderMaterialCenterResults(data)' in javascript
    assert 'function renderMaterialCenterTimeline(items, imageItems, imageIndexById)' in javascript
    assert 'function renderMaterialCenterList(items, imageItems, imageIndexById)' in javascript
    assert 'let materialCenterViewMode = "timeline";' in javascript
    assert 'materialCenterForm?.classList.toggle("hidden", timelineActive);' in javascript
    assert 'materialCenterTimelineViewButton?.setAttribute("aria-selected"' in javascript
    assert 'materialTimelineNodeSummary(dateItems)' in javascript
    assert 'openMaterialCenterPeriod("day", attachment.timeline_date, dateButton)' in javascript
    assert 'downloadAttachmentFile(attachment)' in javascript
    assert 'createAttachmentThumbnail(' in javascript
    assert 'resumeMaterialCenterAfterDrawer()' in javascript

    assert '.material-center-modal {\n  z-index: 319;' in css
    assert '.full-page-life-view {\n  position: fixed;\n  inset: 0;\n  z-index: 125;' in css
    assert '.material-center-card {' in css
    assert '.material-center-results {' in css
    assert 'overflow-y: auto;' in css
    assert '.material-center-card-item {' in css
    assert '.material-center-timeline {' in css
    assert '.material-timeline-date-row {' in css
    assert '.material-timeline-grid {' in css
    assert '.material-timeline-dot {' in css
    assert 'async function runMaterialTimelineAxis({ recenterYears = false } = {})' in javascript
    assert 'function materialTimelineYearWindowCapacity()' in javascript
    assert 'MATERIAL_TIMELINE_YEAR_MIN_WIDTH = 72' in javascript
    assert '/api/v1/materials/timeline/years?start_year=' in javascript
    assert '/api/v1/materials/timeline/months?year=' in javascript
    assert '/api/v1/materials/timeline/days?year=' in javascript
    assert 'function createMaterialTimelineAxisRow({ level, items, yearWindow = null })' in javascript
    assert 'stack.appendChild(createMaterialTimelineAxisRow({ level: "year"' in javascript
    assert 'stack.appendChild(createMaterialTimelineAxisRow({ level: "month"' in javascript
    assert 'stack.appendChild(createMaterialTimelineAxisRow({ level: "day"' in javascript
    assert 'openList.textContent = "在列表中查看当日资料";' in javascript
    assert '.material-time-axis-row.is-year {' in css
    assert '.material-time-axis-track {' in css
    assert '.material-time-axis-page-button {' in css
    assert 'button.disabled = !hasData;' in javascript
    assert 'inlineCount.textContent = `[${totalCount}]`;' in javascript
    assert '.material-time-axis-density,\n.material-time-axis-count {' in css
    assert '/* LifeGraph v0.0.10.5.1：资料中心模式标签页 + 年/月/日三层常驻时间轴 */' in css
    assert '/* LifeGraph v0.0.10.5.2：年月日三层时间轴紧凑化 */' in css
    assert '/* LifeGraph v0.0.10.5.3：三层分段色带时间轴 + 紧凑日内资料条 */' in css
    assert 'background: color-mix(in srgb, var(--axis-color) 31%, #fbfaf6);' in css
    assert '.material-time-axis-track::before {\n  display: none;' in css
    assert 'grid-template-columns: auto minmax(0, 1fr) auto auto;' in css
    assert 'badge.textContent = materialDayTimelineCategoryLabel(attachment);' in javascript
    assert '.material-center-mode-tabs {' in css
    assert '.material-time-axis-stack {' in css
    assert '.material-time-axis-row.is-month {' in css
    assert '.material-time-axis-row.is-day {' in css
    assert 'overflow: hidden;' in css
    assert '.material-center-source-button {' in css
    assert 'text-overflow: ellipsis;' in css


def test_material_center_quick_filter_keeps_category_labels_on_one_line() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    assert ".material-center-keyword" in css
    assert "max-width: 560px" in css
    assert ".material-center-category-options label" in css
    assert "white-space: nowrap" in css
    assert "word-break: keep-all" in css
    assert "min-width: 76px" in css


def test_material_center_truncated_text_has_native_tooltips():
    app_js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert 'title.title = title.textContent;' in app_js
    assert 'meta.title = meta.textContent;' in app_js
    assert 'sourceButton.title = sourceButton.textContent;' in app_js


def test_material_center_supports_independent_import_and_delete() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="importMaterialButton"' in html
    assert 'id="materialImportInput"' in html
    assert 'type="file" multiple' in html
    assert 'async function importIndependentMaterialFile(file, options = {})' in javascript
    assert 'fetch("/api/v1/materials/import"' in javascript
    assert 'formData.append("material_file", file, file.name);' in javascript
    assert 'async function importIndependentMaterials(files)' in javascript
    assert 'independent.textContent = "独立资料 · 直接导入人生资料库";' in javascript
    assert 'if (attachment.is_independent)' in javascript
    assert '`/api/v1/materials/${encodeURIComponent(attachment.id)}`' in javascript
    assert '.material-center-header-actions {' in css
    assert '.material-center-independent-label,' in css


def test_material_directory_scan_preview_and_batch_import_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="scanMaterialDirectoryButton"' in html
    assert 'id="materialDirectoryInput"' in html
    assert 'webkitdirectory' in html
    assert 'id="materialDirectoryScanModal"' in html
    assert 'id="materialDirectoryScanList"' in html
    assert 'id="importScannedMaterials"' in html
    assert 'const MAX_DIRECTORY_SCAN_FILES = 1000;' in javascript
    assert 'window.crypto.subtle.digest("SHA-256"' in javascript
    assert 'api("/api/v1/materials/duplicates"' in javascript
    assert 'sourceRelativePath: item.relativePath' in javascript
    assert 'rejectDuplicate: true' in javascript
    assert 'formData.append("source_relative_path"' in javascript
    assert 'formData.append("reject_duplicate", "true")' in javascript
    assert '.material-directory-scan-modal {' in css
    assert '.material-directory-scan-list {' in css
    assert '.material-directory-scan-item {' in css



def test_material_center_supports_resumable_large_file_uploads() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="largeMaterialUploadPanel"' in html
    assert 'id="largeMaterialUploadList"' in html
    assert 'id="cleanupStaleLargeUploadsButton"' in html
    assert 'value="video" checked> 视频' in html
    assert 'const LARGE_UPLOAD_STORAGE_KEY = "lifegraph.large-material-uploads.v1";' in javascript
    assert 'sessionId: task.sessionId' in javascript
    assert 'filename: task.filename' not in javascript[javascript.index('function persistLargeMaterialUploadTasks()'):javascript.index('function restoreLargeMaterialUploadTasksForCurrentProfile()')]
    assert 'return queueLargeMaterialUploadFile(file, options);' in javascript
    assert 'file.slice(start, end)' in javascript
    assert '/api/v1/materials/large/uploads/${encodeURIComponent(task.sessionId)}/chunks/${index}' in javascript
    assert 'LARGE_UPLOAD_MAX_RETRIES = 3' in javascript
    assert 'const LARGE_UPLOAD_CONCURRENCY = 3;' in javascript
    assert 'Promise.allSettled(Array.from({ length: workerCount }, () => uploadWorker()))' in javascript
    assert 'function formatLargeUploadRate(bytesPerSecond)' in javascript
    assert '预计剩余 ${eta}' in javascript
    assert 'dismiss.textContent = "清理";' in javascript
    assert 'function pauseLargeMaterialUploadTask(task)' in javascript
    assert 'function resumeLargeMaterialUploadTask(task)' in javascript
    assert 'function scheduleLargeMaterialUploadPanelRender(delay = 180)' in javascript
    assert 'task.cancelRequested = true;' in javascript
    assert 'computeLargeMaterialQuickFingerprint(file)' in javascript
    assert 'quick_fingerprint: quickFingerprint || null' in javascript
    assert 'reject_duplicate: options.rejectDuplicate !== false' in javascript
    assert 'focusMaterialCenterImportedAttachment(result);' in javascript
    assert 'row.dataset.timelineDate = String(timelineDate);' in javascript
    assert 'restoreLargeMaterialUploadTasksForCurrentProfile()' in javascript
    assert '/api/v1/materials/large/uploads/maintenance?stale_days=30' in javascript
    assert '/api/v1/materials/large/uploads/cleanup' in javascript
    assert '请选择同一个本地文件继续断点上传' in javascript
    assert 'if (file.size > MAX_LARGE_MATERIAL_BYTES) return "超过 2 TB";' in javascript
    assert 'file.size > MAX_ATTACHMENT_BYTES ? "ready" : "hashing"' in javascript
    assert 'attachment.category === "video" ? "影"' in javascript
    assert '.large-material-upload-panel {' in css
    assert '.large-material-upload-progress {' in css
    assert '.material-center-file-icon.is-video {' in css
    assert '.material-timeline-date-row.is-upload-focus' in css


def test_period_materials_default_to_six_item_collapsed_view() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="materialSectionToggle"' in html
    assert 'id="materialSectionLoadMore"' in html
    assert 'const MATERIAL_SECTION_COLLAPSED_LIMIT = 6;' in javascript
    assert 'const PERIOD_MATERIAL_PAGE_SIZE = 12;' in javascript
    assert 'materialSectionExpanded = false;' in javascript
    assert 'index >= MATERIAL_SECTION_COLLAPSED_LIMIT' in javascript
    assert 'materialSectionTotal = Number(options.total ?? materialSectionTotal ?? items.length);' in javascript
    assert 'const total = Math.max(materialSectionTotal, cards.length);' in javascript
    assert '`展开已加载（${cards.length}/${total}）`' in javascript
    assert '`继续加载（${cards.length}/${total}）`' in javascript
    assert '/materials?limit=${PERIOD_MATERIAL_PAGE_SIZE}&offset=${offset}' in javascript
    assert 'remaining <= 280' in javascript
    assert 'function ensureMaterialSectionToggle()' in javascript
    assert 'materialSectionToggle.dataset.collapseBound' in javascript
    assert '.material-section-toggle {' in css


def test_material_center_timeline_groups_collapse_after_six_items() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'function bindMaterialTimelineCollapse(' in javascript
    assert 'toggle.textContent = `展开全部（${items.length}）`;' in javascript
    assert 'toggle.textContent = expanded ? "收起" : `展开全部（${items.length}）`;' in javascript
    assert 'card.classList.toggle("hidden", index >= MATERIAL_SECTION_COLLAPSED_LIMIT);' in javascript
    assert 'bindMaterialTimelineCollapse(grid, dateItems, nodeHeader, imageItems, imageIndexById);' in javascript
    assert 'bindMaterialTimelineCollapse(grid, undated, heading, imageItems, imageIndexById);' in javascript
    assert '.material-timeline-node-header {' in css
    assert '.material-timeline-toggle {' in css


def test_material_timeline_year_can_collapse_all_year_materials() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'yearHeadingText.textContent = `${year} 年 · ${yearItems.length} 份资料`;' in javascript
    assert 'yearToggle.textContent = "收起年度";' in javascript
    assert 'yearBody.classList.toggle("hidden", !yearExpanded);' in javascript
    assert 'yearToggle.textContent = yearExpanded ? "收起年度" : `展开年度（${yearItems.length}）`;' in javascript
    assert 'yearToggle.setAttribute("aria-expanded", String(yearExpanded));' in javascript
    assert '.material-timeline-year-toggle {' in css
    assert '.material-timeline-year-body {' in css


def test_material_timeline_month_has_independent_collapse_control() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'monthHeadingText.textContent = `${Number(month)} 月 · ${monthItems.length} 份资料`;' in javascript
    assert 'monthToggle.textContent = "收起月份";' in javascript
    assert 'monthBody.classList.toggle("hidden", !monthExpanded);' in javascript
    assert 'monthToggle.textContent = monthExpanded ? "收起月份" : `展开月份（${monthItems.length}）`;' in javascript
    assert 'monthToggle.setAttribute("aria-expanded", String(monthExpanded));' in javascript
    assert '.material-timeline-month-toggle {' in css
    assert '.material-timeline-month-body {' in css


def test_period_drawer_add_buttons_include_current_scope() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'function periodScopeLabel(scope = selectedScope)' in javascript
    assert 'if (scope === "year") return "年";' in javascript
    assert 'if (scope === "month") return "月";' in javascript
    assert 'if (scope === "day") return "日";' in javascript
    assert 'return `＋ 添加${periodScopeLabel(scope)}${config.itemLabel}`;' in javascript
    assert 'toggleEventFormButton.textContent = scopedContentCreateLabel("event", detail.scope);' in javascript
    assert 'toggleMemoryFormButton.textContent = scopedContentCreateLabel("memory", detail.scope);' in javascript
    assert ': scopedContentCreateLabel("plan", detail.scope);' in javascript


def test_period_drawer_content_lists_have_independent_collapse_controls() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="eventListToggle"' in html
    assert 'id="memoryListToggle"' in html
    assert 'id="planListToggle"' in html
    assert 'const contentSectionCollapsed = { event: false, memory: false, plan: false };' in javascript
    assert 'function updateContentListCollapse(kind)' in javascript
    assert 'list.classList.toggle("hidden", collapsed);' in javascript
    assert '`展开${config.itemLabel}（${itemCount}）`' in javascript
    assert '`收起${config.itemLabel}`' in javascript
    assert 'contentSectionCollapsed[kind] = !contentSectionCollapsed[kind];' in javascript
    assert '.content-section-toggle {' in css


def test_home_hero_contains_clickable_current_month_calendar() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="homeMonthCalendarTitle"' in html
    assert 'id="homeMonthCalendarGrid"' in html
    assert '<span>一</span><span>二</span><span>三</span><span>四</span><span>五</span><span>六</span><span>日</span>' in html
    assert 'function renderHomeMonthCalendar()' in javascript
    assert 'if (!homeMonthCalendarMonthKey) homeMonthCalendarMonthKey = todayMonthKey;' in javascript
    assert 'const mondayOffset = (firstDay.getUTCDay() + 6) % 7;' in javascript
    assert 'const button = periodChildButton(child, currentProgress.today);' in javascript
    assert 'renderHomeMonthCalendar();' in javascript
    assert '.hero-month-calendar {' in css
    assert '.hero-month-calendar-grid {' in css
    assert 'grid-template-columns: repeat(7, minmax(0, 1fr));' in css


def test_home_hero_uses_balanced_side_tracks_for_centered_month_calendar():
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")
    assert "grid-template-columns: minmax(260px, 1fr) minmax(360px, 520px) minmax(260px, 1fr);" in css
    assert ".hero > .life-percent {\n  justify-self: end;" in css
    assert ".hero-copy {\n  min-width: 0;\n  justify-self: start;" in css
    assert ".hero-month-calendar {\n  width: 100%;\n  justify-self: center;" in css


def test_day_calendars_use_horizontal_lunar_watermark_without_growing_home_cells() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert '/assets/calendar_meta.js?v=0.0.10' in html
    assert '/assets/app.js?v=0.0.10' in html
    assert 'function decorateDayCalendarButton(button, child, options = {})' in javascript
    assert 'window.LifeGraphCalendarMeta?.getDateMeta?.(child.period_key)' in javascript
    assert 'watermark.className = "calendar-day-watermark";' in javascript
    assert 'watermark.classList.add(`glyph-count-${watermarkCharacters.length}`);' in javascript
    assert 'solarDay.className = "calendar-day-solar";' in javascript
    assert 'decorateDayCalendarButton(button, child)' in javascript
    assert 'decorateDayCalendarButton(button, child, { actionLabel: "点击查看或添加" })' in javascript
    assert '.calendar-day-watermark {' in css
    assert '.calendar-day-watermark.glyph-count-2 .glyph-1 { left: 28%; }' in css
    assert '.calendar-day-solar {' in css
    assert 'z-index: 2;' in css
    assert '.period-navigator[data-scope="month"] .calendar-day-watermark,' in css
    assert '.period-navigator[data-scope="day"] .calendar-day-watermark {' in css
    assert '.hero-month-calendar-grid .period-child-cell,\n.hero-month-day-placeholder {\n  height: 27px;' in css


def test_calendar_meta_supports_lunar_first_day_and_solar_terms_locally() -> None:
    calendar_meta = (PROJECT_ROOT / "frontend" / "calendar_meta.js").read_text(encoding="utf-8")

    assert '"初一"' in calendar_meta
    assert '"立秋"' in calendar_meta
    assert 'lunar.dayNumber === 1 ? lunar.monthName : lunar.dayName' in calendar_meta
    assert 'tooltipParts.push(`农历${lunarFull}`);' in calendar_meta
    assert 'tooltipParts.push(`节气：${solarTerm}`);' in calendar_meta
    assert 'global.LifeGraphCalendarMeta = api;' in calendar_meta


def test_home_month_calendar_title_opens_year_month_picker() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="homeMonthCalendarPickerButton"' in html
    assert 'id="homeMonthCalendarPicker"' in html
    assert 'id="homeMonthCalendarYear"' in html
    assert 'id="homeMonthCalendarMonth"' in html
    assert 'id="homeMonthCalendarToday"' in html
    assert 'id="homeMonthCalendarApply"' in html
    assert 'function syncHomeMonthCalendarPicker()' in javascript
    assert 'function setHomeMonthCalendarMonth(monthKey' in javascript
    assert 'homeMonthCalendarYear?.addEventListener("change"' in javascript
    assert 'setHomeMonthCalendarMonth(currentProgress.today.slice(0, 7));' in javascript
    assert '.hero-month-calendar-picker-popover {' in css
    assert '.hero-month-calendar-title-button[aria-expanded="true"]' in css


def test_calendar_meta_supports_major_traditional_festivals_and_priority() -> None:
    calendar_meta = (PROJECT_ROOT / "frontend" / "calendar_meta.js").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    for festival in ["春节", "元宵", "清明", "端午", "七夕", "中秋", "重阳", "腊八", "除夕"]:
        assert f'"{festival}"' in calendar_meta
    assert "festival || solarTerm ||" in calendar_meta
    assert 'tooltipParts.push(`传统节日：${festival}`);' in calendar_meta
    assert 'watermark.classList.toggle("is-festival", Boolean(calendarMeta.festival));' in javascript
    assert ".calendar-day-watermark.is-festival {" in css
    assert "color: #a94339;" in css
    assert ".calendar-day-watermark.is-solar-term {" in css
    assert "color: #ad5d50;" in css


def test_material_center_uses_paged_loading_and_lazy_thumbnails() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'params.set("limit", "48")' in javascript
    assert 'params.set("offset", "0")' in javascript
    assert 'async function loadMoreMaterialCenterResults()' in javascript
    assert 'new IntersectionObserver' in javascript
    assert 'observeMaterialThumbnail(button, loadThumbnail)' in javascript
    assert 'material-center-load-sentinel' in javascript
    assert '滚动继续加载' in html
    assert '.material-center-load-sentinel {' in css


def test_global_toast_stays_above_material_center_and_other_overlays() -> None:
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "/* LifeGraph v0.0.9.3.2：全局提示始终显示在弹窗/遮罩层之上 */" in css
    assert ".toast {\n  z-index: 1200;\n  pointer-events: none;\n}" in css
    assert ".material-center-modal {\n  z-index: 319;" in css
    assert ".attachment-preview-modal {\n  position: fixed;\n  inset: 0;\n  z-index: 500;" in css


def test_video_material_metadata_preview_and_mkv_fallback_are_wired() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert "async function extractNativeVideoAssets(file)" in javascript
    assert "async function extractMatroskaVideoMetadata(file)" in javascript
    assert '"V_MPEGH/ISO/HEVC": "H.265 / HEVC"' in javascript
    assert "async function generateVideoInfoPoster(file, metadata)" in javascript
    assert "/video-metadata`" in javascript
    assert "/preview`" in javascript
    assert "function createVideoThumbnail(attachment" in javascript
    assert "videoTechnicalMetaParts(attachment)" in javascript
    assert ".video-thumbnail {" in css
    assert ".video-thumbnail-duration {" in css


def test_video_player_uses_scoped_ticket_and_http_range_stream() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="videoPlayerModal"' in html
    assert 'id="videoPlayer" class="video-player" controls playsinline preload="metadata"' in html
    assert 'id="downloadVideoPlayer"' in html
    assert 'async function requestAttachmentStreamTicket(attachment)' in javascript
    assert '/playback-ticket`' in javascript
    assert '/stream?${params.toString()}`' in javascript
    assert 'function openVideoPlayer(attachment' in javascript
    assert 'videoPlayer?.addEventListener("seeking"' in javascript
    assert '正在定位并解密目标分块' in javascript
    assert 'Range 播放通道已建立' in javascript
    assert 'preview.addEventListener("click"' in javascript
    assert 'download.textContent = "下载";' in javascript
    assert 'download.disabled = true;' not in javascript
    assert '.video-player-modal {' in css
    assert 'z-index: 700;' in css
    assert 'body.video-player-open {' in css


def test_video_player_audio_compat_layer_detects_dts_and_syncs_separate_audio() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="videoCompatAudio" class="video-compat-audio"' in html
    assert 'id="videoAudioCompatStatus"' in html
    assert 'id="videoAudioCompatAction"' in html
    assert '"A_DTS": "DTS"' in javascript
    assert 'metadata.audio_codec_id = result.audioCodecId;' in javascript
    assert '/audio-compat`' in javascript
    assert '/audio-compat/stream?${params.toString()}`' in javascript
    assert 'async function prepareVideoAudioCompatibility' in javascript
    assert 'function syncCompatAudioFromVideo' in javascript
    assert 'videoPlayer?.addEventListener("volumechange"' in javascript
    assert 'videoPlayer?.addEventListener("ratechange"' in javascript
    assert 'videoCompatAudio?.addEventListener("error"' in javascript
    assert '.video-compat-audio {' in css
    assert '.video-audio-compat-status {' in css



def test_audio_compat_progress_shows_rate_and_eta() -> None:
    app_js = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "videoAudioCompatRateSample" in app_js
    assert "formatLargeUploadRate(speedBps)" in app_js
    assert "预计剩余" in app_js


def test_backup_errors_preserve_server_detail() -> None:
    project_root = Path(__file__).resolve().parents[1]
    javascript = (project_root / "frontend" / "app.js").read_text(encoding="utf-8")
    assert 'preferServerDetail.has(error?.code)' in javascript
    assert '"BACKUP_EXPORT_FAILED"' in javascript
    assert '"AUTO_BACKUP_FAILED"' in javascript


def test_media_backup_panel_supports_incremental_sync_and_verify() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="mediaBackupTargetPath"' in html
    assert 'id="startMediaBackupButton"' in html
    assert 'id="verifyMediaBackupButton"' in html
    assert 'id="verifyMediaLibraryButton"' in html
    assert 'id="cancelMediaBackupButton"' in html
    assert '增量备份媒体库' in html
    assert '/api/v1/backup/media/${mode}' in javascript
    assert '/api/v1/backup/media/verify-library' in javascript
    assert '/api/v1/backup/media/cancel' in javascript
    assert '媒体分块 ${chunks} 个' in javascript
    assert '.media-backup-controls {' in css


def test_material_center_year_and_month_click_auto_select_latest_material_day() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")

    assert 'let materialTimelineAxisAutoResolve = null;' in javascript
    assert 'function resetMaterialTimelineAxisToToday()' in javascript
    assert 'if (materialCenterViewMode === "timeline") resetMaterialTimelineAxisToToday();' in javascript
    assert 'materialTimelineAxisAutoResolve = "year";' in javascript
    assert 'materialTimelineAxisAutoResolve = "month";' in javascript
    assert 'function materialTimelineLatestDataValue(items, field)' in javascript
    assert 'const latestMonth = materialTimelineLatestDataValue(monthItems, "month");' in javascript
    assert 'materialTimelineAxisDay = materialTimelineLatestDataValue(dayItems, "day");' in javascript
    assert 'const [years, months] = await Promise.all([' in javascript
    assert 'const days = await api(' in javascript


def test_material_center_day_selection_expands_vertical_intraday_axis() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'function createMaterialDayTimeAxis(dayData, dayCount)' in javascript
    assert 'function createMaterialDayTimelineEntry(attachment, allItems, itemIndex)' in javascript
    assert '/api/v1/materials/timeline/hours?date=${encodeURIComponent(isoDate)}' in javascript
    assert '/api/v1/materials/timeline/minutes?date=${encodeURIComponent(isoDate)}' in javascript
    assert 'MATERIAL_TIMELINE_DAY_PAGE_SIZE' in javascript
    assert 'detailHost.appendChild(createMaterialDayTimeAxis(dayDetail, dayItems.length));' in javascript
    assert 'section.style.setProperty("--day-axis-x"' in javascript
    assert 'section.classList.toggle("is-left-facing", selectedDay > safeDayCount / 2);' in javascript
    assert 'startCap.textContent = "00:00";' in javascript
    assert 'endCap.textContent = "24:00";' in javascript
    assert 'time.textContent = materialDayTimelineTimeText(attachment.timeline_at, attachment.time_precision)' in javascript
    assert 'openAttachmentPreview(allItems, itemIndex, action)' in javascript
    assert 'openVideoPlayer(attachment, action)' in javascript
    assert 'function materialDayTimelineBucketMode(minuteItems)' in javascript
    assert 'MATERIAL_TIMELINE_MINUTE_GROUP_THRESHOLD' in javascript
    assert 'function loadMoreMaterialTimelineDay()' in javascript
    assert 'previous_date' in javascript
    assert 'next_date' in javascript
    assert '上一有资料日期' in javascript
    assert '下一有资料日期' in javascript

    assert '/* LifeGraph v0.0.10.5：选中日期向下展开纵向日内时间轴 */' in css
    assert '.material-day-time-axis {' in css
    assert 'left: var(--day-axis-x);' in css
    assert '.material-day-time-entry {' in css
    assert '.material-day-time-card {' in css
    assert '.material-day-time-axis.is-left-facing .material-day-time-card {' in css


def test_home_metrics_are_compact_and_embedded_in_hero() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    hero_start = html.index('<section class="hero panel">')
    hero_end = html.index('</section>', html.index('</section>', hero_start) + len('</section>'))
    hero_slice = html[hero_start:hero_end]

    assert 'class="metric-grid hero-metrics"' in hero_slice
    assert 'class="metric-card hero-metric-item"' in hero_slice
    assert 'class="metric-card panel"' not in html
    assert '.hero > .hero-metrics {' in css
    assert 'min-height: 34px;' in css
    assert 'font-size: clamp(1.08rem, 2vw, 1.42rem);' in css


def test_material_center_dense_day_supports_aggregation_continue_load_and_neighbor_navigation() -> None:
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'const MATERIAL_TIMELINE_DAY_PAGE_SIZE = 100;' in javascript
    assert 'const MATERIAL_TIMELINE_MINUTE_GROUP_THRESHOLD = 4;' in javascript
    assert 'if (occupiedMinutes > 720) return "hour";' in javascript
    assert 'if (occupiedMinutes > 240) return "ten-minute";' in javascript
    assert 'className = "material-day-time-group"' in javascript
    assert 'button.textContent = materialTimelineDayLoadingMore ? "加载中…" : "继续加载";' in javascript
    assert 'selectMaterialTimelineIsoDate(previousDate)' in javascript
    assert 'selectMaterialTimelineIsoDate(nextDate)' in javascript
    assert 'content-visibility: auto;' in css
    assert '.material-day-time-group-card {' in css
    assert '.material-time-axis-day-navigation {' in css


def test_material_center_has_persistent_auto_scan_source_manager() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="manageMaterialScanSourcesButton"' in html
    assert '>自动扫描</button>' in html
    assert '>手动扫描目录</button>' in html
    assert 'id="materialAutoScanModal"' in html
    assert 'id="materialScanSourcePath"' in html
    assert 'id="startMaterialScanner"' in html
    assert 'id="pauseMaterialScanner"' in html
    assert 'function openMaterialAutoScanModal()' in javascript
    assert '/api/v1/materials/scan-sources' in javascript
    assert '/api/v1/materials/scanner/start' in javascript
    assert '/api/v1/materials/scanner/pause' in javascript
    assert '解锁后自动执行一次增量扫描' in html
    assert '/* LifeGraph v0.0.10.7：本机自动扫描源与增量扫描 */' in css
    assert '.material-auto-scan-modal {' in css
    assert 'z-index: 420;' in css


def test_material_time_review_and_manual_correction_ui_are_present() -> None:
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    javascript = (PROJECT_ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    css = (PROJECT_ROOT / "frontend" / "styles.css").read_text(encoding="utf-8")

    assert 'id="reviewMaterialTimeButton"' in html
    assert 'id="materialTimeCorrectionModal"' in html
    assert 'id="materialTimeCorrectionDate"' in html
    assert 'id="materialTimeCorrectionTime"' in html
    assert '<i class="material-dot"></i>有资料' in html
    assert 'params.set("time_status", materialCenterTimeStatus);' in javascript
    assert 'correctTimeButton.textContent = "修正时间";' in javascript
    assert '/timeline`' in javascript
    assert 'timeline_time: materialTimeCorrectionTime.value || null' in javascript
    assert 'if (source === "manual") return "手工确认时间";' in javascript
    assert '.material-time-correction-modal {' in css
    assert '.material-time-review-button.is-active {' in css
    assert '.material-dot {' in css


def test_drawer_material_load_more_is_below_material_list():
    html = (PROJECT_ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    list_pos = html.index('id="materialList"')
    load_more_pos = html.index('id="materialSectionLoadMore"')
    heading_pos = html.index('id="materialSectionHeading"')
    assert heading_pos < list_pos < load_more_pos
    assert 'class="material-section-toggle material-section-load-more hidden"' in html
