from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")


def test_custom_confirmation_dialog_replaces_native_confirm() -> None:
    html = read("frontend/index.html")
    javascript = read("frontend/app.js")

    assert 'id="confirmModal"' in html
    assert 'id="confirmCancel"' in html
    assert 'id="confirmAccept"' in html
    assert "function askConfirmation" in javascript
    assert "function closeConfirmation" in javascript
    assert "window.confirm" not in javascript


def test_unsaved_form_changes_are_guarded() -> None:
    javascript = read("frontend/app.js")

    assert "function contentFormSnapshot" in javascript
    assert "function hasUnsavedContentChanges" in javascript
    assert "async function confirmDiscardChanges" in javascript
    assert 'window.addEventListener("beforeunload"' in javascript
    assert "requestCloseDateDrawer" in javascript


def test_content_operations_show_busy_and_friendly_feedback() -> None:
    html = read("frontend/index.html")
    javascript = read("frontend/app.js")
    css = read("frontend/styles.css")

    assert 'aria-live="polite"' in html
    assert "function setButtonBusy" in javascript
    assert "function friendlyErrorMessage" in javascript
    assert 'showToast(config.deleteMessage, "success")' in javascript
    assert 'setButtonBusy(button, true, "恢复中…")' in javascript
    assert 'submit.textContent = editId ? "保存修改中…" : "加密保存中…";' in javascript
    assert "button.is-busy::before" in css
    assert '.toast[data-tone="error"]' in css


def test_date_detail_uses_three_compact_quick_actions() -> None:
    html = read("frontend/index.html")
    javascript = read("frontend/app.js")
    css = read("frontend/styles.css")

    assert 'id="contentActionBar"' in html
    assert html.index('id="toggleEventForm"') < html.index('id="eventSection"')
    assert html.index('id="toggleMemoryForm"') < html.index('id="memorySection"')
    assert html.index('id="togglePlanForm"') < html.index('id="planSection"')
    assert 'class="content-action-bar"' in html
    assert "function updateContentSectionVisibility" in javascript
    assert 'config.section.classList.toggle("hidden", itemCount === 0 && !formOpen)' in javascript
    assert 'empty.className = "content-empty-state"' not in javascript
    assert ".content-action-bar" in css
    assert "grid-template-columns: repeat(3, minmax(0, 1fr))" in css


def test_mobile_actions_and_confirmation_are_compact() -> None:
    css = read("frontend/styles.css")

    assert "@media (max-width: 620px)" in css
    assert ".confirm-actions" in css
    assert ".content-card-actions button" in css
    assert ".event-form-actions" in css


def test_content_card_actions_are_grouped_in_more_menu() -> None:
    javascript = read("frontend/app.js")
    css = read("frontend/styles.css")

    assert 'moreButton.className = "content-more-button"' in javascript
    assert 'moreButton.textContent = "⋯";' in javascript
    assert 'moreButton.setAttribute("aria-haspopup", "menu")' in javascript
    assert 'menu.className = "content-more-menu hidden"' in javascript
    assert 'menu.setAttribute("role", "menu")' in javascript
    assert 'editButton.setAttribute("role", "menuitem")' in javascript
    assert 'deleteButton.setAttribute("role", "menuitem")' in javascript
    assert "function closeOpenContentMenu" in javascript
    assert "function toggleContentMenu" in javascript
    assert 'if (openContentMenu)' in javascript
    assert ".content-more-button {" in css
    assert ".content-more-menu {" in css
    assert ".content-menu-item.content-edit-button" in css
