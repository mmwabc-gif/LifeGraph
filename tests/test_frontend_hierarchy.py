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

    assert 'const frontendBuildVersion = "0.0.2"' in javascript
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
