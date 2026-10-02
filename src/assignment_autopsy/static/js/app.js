/* Translations live in locales/<lang>/LC_MESSAGES/messages.po; the server
   injects the active catalog as window.I18N (see base.html / i18n.py). */
const LANGUAGE_KEY = "assignment-language";
const THEME_KEY = "assignment-theme";
const catalog = window.I18N || {};
const currentLanguage = () => window.I18N_LANG || "es";
const t = (message) => catalog[message] || message;
const root = document.documentElement;
const csrfToken = () => document.querySelector('meta[name="csrf-token"]')?.content || "";

/* Exact-match translation (never substring) so user content such as titles or
   descriptions can't be rewritten; inputs/textareas/scripts are skipped. */
const translatePage = () => {
	if (!Object.keys(catalog).length) return;
	const swap = (value) => {
		const trimmed = value.trim();
		return trimmed && catalog[trimmed] ? value.replace(trimmed, catalog[trimmed]) : value;
	};
	const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
		acceptNode: (node) => ["SCRIPT", "STYLE", "TEXTAREA", "CODE"].includes(node.parentElement?.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT,
	});
	const nodes = [];
	while (walker.nextNode()) nodes.push(walker.currentNode);
	nodes.forEach((node) => { node.nodeValue = swap(node.nodeValue); });
	document.querySelectorAll("[placeholder], [aria-label], [title], [data-tip]").forEach((element) => {
		["placeholder", "aria-label", "title", "data-tip"].forEach((attribute) => {
			const value = element.getAttribute(attribute);
			if (value) element.setAttribute(attribute, swap(value));
		});
	});
};
translatePage();

/* ---- Theme + language (chosen in Settings > Appearance) ---- */
const currentTheme = () => (root.classList.contains("dark-mode") ? "dark" : "light");
const applyTheme = (mode) => {
	root.classList.toggle("dark-mode", mode === "dark");
	localStorage.setItem(THEME_KEY, mode);
	syncAppearanceOptions();
};
function syncAppearanceOptions() {
	document.querySelectorAll("[data-theme-option]").forEach((b) => b.classList.toggle("is-active", b.dataset.themeOption === currentTheme()));
	document.querySelectorAll("[data-language-option]").forEach((b) => b.classList.toggle("is-active", b.dataset.languageOption === currentLanguage()));
}
document.addEventListener("click", (event) => {
	const theme = event.target.closest("[data-theme-option]");
	if (theme) applyTheme(theme.dataset.themeOption);
	const language = event.target.closest("[data-language-option]");
	if (language && language.dataset.languageOption !== currentLanguage()) {
		localStorage.setItem(LANGUAGE_KEY, language.dataset.languageOption);
		document.cookie = `${LANGUAGE_KEY}=${language.dataset.languageOption}; path=/; max-age=31536000; SameSite=Lax`;
		// Only reopen the settings dialog on reload when it actually exists (logged-in shell).
		if (document.getElementById("settings-modal")) window.location.hash = "#settings/appearance";
		window.location.reload();
	}
});
syncAppearanceOptions();

/* ---- Small helpers: toast + JSON form posts ---- */
function toast(message, kind = "info") {
	let stack = document.querySelector(".toast-stack");
	if (!stack) {
		stack = document.createElement("div");
		stack.className = "toast-stack";
		stack.setAttribute("role", "status");
		document.body.append(stack);
	}
	const element = document.createElement("div");
	element.className = `toast toast-${kind}`;
	element.textContent = message;
	stack.append(element);
	setTimeout(() => { element.classList.add("is-leaving"); setTimeout(() => element.remove(), 250); }, 3800);
}

async function postForm(url, formData) {
	if (!formData.has("csrf_token")) formData.set("csrf_token", csrfToken());
	let data = {};
	try {
		const response = await fetch(url, { method: "POST", body: formData, headers: { Accept: "application/json" }, credentials: "same-origin" });
		data = await response.json().catch(() => ({}));
		if (!response.ok && data.ok === undefined) data = { ok: false, error: typeof data.detail === "string" ? data.detail : "Algo salió mal. Inténtalo de nuevo." };
	} catch {
		data = { ok: false, error: "Algo salió mal. Inténtalo de nuevo." };
	}
	return data;
}

/* ---- Loading state for "Guardar"-style buttons: swap the label for bouncing dots ---- */
function setButtonLoading(button, loading) {
	if (!button) return;
	if (loading) {
		if (button.dataset.loadingLabel === undefined) button.dataset.loadingLabel = button.innerHTML;
		button.disabled = true;
		button.classList.add("is-loading");
		button.innerHTML = '<span class="dot-loader"><span></span><span></span><span></span></span>';
	} else {
		button.disabled = false;
		button.classList.remove("is-loading");
		if (button.dataset.loadingLabel !== undefined) {
			button.innerHTML = button.dataset.loadingLabel;
			delete button.dataset.loadingLabel;
		}
	}
}
/* Plain (non-fetch) form submits still take a moment server-side (uploads, hashing...)
   before the browser navigates away, so show the same loading state for those too.
   Forms handled via fetch (data-json-form) manage their own button state instead. */
document.addEventListener("submit", (event) => {
	const form = event.target;
	if (!(form instanceof HTMLFormElement) || form.hasAttribute("data-json-form")) return;
	setButtonLoading(event.submitter || form.querySelector("button:not([type=button])"), true);
});


/* ---- Tooltips for the team rail (it scrolls, so tooltips can't be CSS-only) ---- */
const tooltip = document.createElement("div");
tooltip.className = "tooltip";
tooltip.hidden = true;
document.body.append(tooltip);
document.addEventListener("mouseover", (event) => {
	const target = event.target.closest?.("[data-tip]");
	if (!target) { tooltip.hidden = true; return; }
	tooltip.textContent = target.dataset.tip;
	const box = target.getBoundingClientRect();
	tooltip.style.left = `${box.right + 10}px`;
	tooltip.style.top = `${box.top + box.height / 2}px`;
	tooltip.hidden = false;
});
document.addEventListener("scroll", () => { tooltip.hidden = true; }, true);
document.addEventListener("click", () => { tooltip.hidden = true; });

/* ---- Mobile drawer (rail + channel list), Discord-style ---- */
const appShell = document.querySelector(".app-shell");
const isPhone = () => window.matchMedia("(max-width: 760px)").matches;
const setDrawer = (open) => appShell?.classList.toggle("sidebar-open", open);
document.querySelector("[data-sidebar-toggle]")?.addEventListener("click", () => setDrawer(!appShell.classList.contains("sidebar-open")));
appShell?.addEventListener("click", (event) => {
	// The dimmed backdrop is a pseudo-element of the shell itself.
	if (event.target === appShell) setDrawer(false);
	if (event.target.closest("[data-open-modal], [data-open-settings]")) setDrawer(false);
});
let swipeStart = null;
document.addEventListener("touchstart", (event) => {
	const touch = event.touches[0];
	swipeStart = isPhone() && event.touches.length === 1 ? { x: touch.clientX, y: touch.clientY } : null;
}, { passive: true });
document.addEventListener("touchend", (event) => {
	if (!swipeStart || !appShell) return;
	const touch = event.changedTouches[0];
	const dx = touch.clientX - swipeStart.x;
	const dy = touch.clientY - swipeStart.y;
	const open = appShell.classList.contains("sidebar-open");
	if (Math.abs(dx) > 70 && Math.abs(dx) > Math.abs(dy) * 1.6) {
		if (!open && dx > 0 && swipeStart.x < 40) setDrawer(true);
		else if (open && dx < 0) setDrawer(false);
	}
	swipeStart = null;
}, { passive: true });
// Land on the team list first on the home screen, once per browser tab session.
if (appShell && isPhone() && location.pathname === "/groups" && !sessionStorage.getItem("drawer-seen")) {
	sessionStorage.setItem("drawer-seen", "1");
	setDrawer(true);
}

/* ---- Right-click quick-edit menu for cards (assignments, teams...), like Discord ---- */
const contextMenu = document.createElement("div");
contextMenu.className = "context-menu";
contextMenu.hidden = true;
document.body.append(contextMenu);
function closeContextMenu() { contextMenu.hidden = true; }
function submitContextAction(action) {
	const form = document.createElement("form");
	form.method = "post";
	form.action = action;
	form.hidden = true;
	form.innerHTML = `<input type="hidden" name="csrf_token" value="${csrfToken()}">`;
	document.body.append(form);
	form.requestSubmit();
}
function openContextMenu(card, x, y) {
	let items;
	try { items = JSON.parse(card.dataset.contextMenu); } catch { items = null; }
	if (!items?.length) { closeContextMenu(); return false; }
	contextMenu.replaceChildren(...items.map((item) => {
		const button = document.createElement("button");
		button.type = "button";
		button.className = item.danger ? "context-menu-item danger" : "context-menu-item";
		button.textContent = t(item.label);
		button.addEventListener("click", () => {
			closeContextMenu();
			if (item.confirm && !window.confirm(t(item.confirm))) return;
			if (item.action) submitContextAction(item.action);
			else if (item.href) window.location.href = item.href;
		});
		return button;
	}));
	contextMenu.hidden = false;
	const bounds = contextMenu.getBoundingClientRect();
	contextMenu.style.left = `${Math.max(8, Math.min(x, window.innerWidth - bounds.width - 8))}px`;
	contextMenu.style.top = `${Math.max(8, Math.min(y, window.innerHeight - bounds.height - 8))}px`;
	return true;
}
document.addEventListener("contextmenu", (event) => {
	const card = event.target.closest("[data-context-menu]");
	if (!card) { closeContextMenu(); return; }
	if (openContextMenu(card, event.clientX, event.clientY)) event.preventDefault();
});
/* Touch screens: long-press opens the same menu (iOS never fires `contextmenu`). */
let longPress = null;
let suppressClickUntil = 0;
document.addEventListener("touchstart", (event) => {
	const card = event.target.closest("[data-context-menu]");
	if (!card || event.touches.length !== 1) return;
	const { clientX, clientY } = event.touches[0];
	longPress = setTimeout(() => {
		longPress = null;
		if (openContextMenu(card, clientX, clientY)) {
			suppressClickUntil = Date.now() + 700;
			navigator.vibrate?.(15);
		}
	}, 500);
}, { passive: true });
const cancelLongPress = () => { if (longPress) { clearTimeout(longPress); longPress = null; } };
document.addEventListener("touchmove", cancelLongPress, { passive: true });
document.addEventListener("touchend", cancelLongPress, { passive: true });
document.addEventListener("touchcancel", cancelLongPress, { passive: true });
// Capture phase so the card link doesn't navigate and the menu isn't instantly closed.
document.addEventListener("click", (event) => {
	if (Date.now() < suppressClickUntil) { event.preventDefault(); event.stopPropagation(); }
}, true);
document.addEventListener("click", closeContextMenu);
document.addEventListener("scroll", closeContextMenu, true);
window.addEventListener("blur", closeContextMenu);
document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeContextMenu(); });

/* ==========================================================================
   Modals (team dialog, settings pop-up, cropper)
   ========================================================================== */
function openModal(modal) {
	if (!modal) return;
	modal.hidden = false;
	modal._returnFocus = document.activeElement;
	document.body.classList.add("modal-open");
	modal.querySelector("input:not([type=hidden]):not([type=search]):not([type=file])")?.focus({ preventScroll: true });
}
function closeModal(modal) {
	if (!modal) return;
	if (modal._beforeClose && modal._beforeClose() === false) return;
	modal.hidden = true;
	if (!document.querySelector(".modal-backdrop:not([hidden])")) document.body.classList.remove("modal-open");
	modal._returnFocus?.focus?.({ preventScroll: true });
}
let backdropPressed = false;
document.addEventListener("mousedown", (event) => { backdropPressed = event.target.classList?.contains("modal-backdrop") || false; });
document.addEventListener("click", (event) => {
	const opener = event.target.closest("[data-open-modal]");
	if (opener) { openModal(document.getElementById(opener.dataset.openModal)); return; }
	if (event.target.closest("[data-close-modal]")) { closeModal(event.target.closest(".modal-backdrop")); return; }
	if (backdropPressed && event.target.classList.contains("modal-backdrop")) (event.target._close || (() => closeModal(event.target)))();
});
document.addEventListener("keydown", (event) => {
	if (event.key !== "Escape") return;
	const open = [...document.querySelectorAll(".modal-backdrop:not([hidden])")].pop();
	if (open) (open._close || (() => closeModal(open)))();
});
document.querySelectorAll("[data-tab]").forEach((tab) => tab.addEventListener("click", () => {
	const dialog = tab.closest(".dialog");
	dialog.querySelectorAll("[data-tab]").forEach((other) => other.classList.toggle("is-active", other === tab));
	dialog.querySelectorAll("[data-tab-panel]").forEach((panel) => { panel.hidden = panel.dataset.tabPanel !== tab.dataset.tab; });
	dialog.querySelector(`[data-tab-panel="${tab.dataset.tab}"] input:not([type=hidden])`)?.focus();
}));

/* ---- Settings pop-up ---- */
const settingsModal = document.getElementById("settings-modal");
let pendingAvatar = null;
if (settingsModal) {
	const titles = { account: t("Cuenta"), profile: t("Perfil"), appearance: t("Apariencia") };
	const scrollBox = settingsModal.querySelector(".settings-scroll");
	const unsavedBar = settingsModal.querySelector("[data-unsaved-bar]");
	function showSettingsPage(name) {
		settingsModal.querySelectorAll(".settings-page").forEach((page) => { page.hidden = page.dataset.page !== name; });
		settingsModal.querySelectorAll(".settings-link[data-settings-page], .settings-user").forEach((link) => link.classList.toggle("is-active", link.dataset.settingsPage === name && link.classList.contains("settings-link")));
		settingsModal.querySelector("[data-settings-title]").textContent = titles[name] || "";
		scrollBox.scrollTop = 0;
	}
	settingsModal._beforeClose = () => {
		if (!pendingAvatar) return true;
		unsavedBar.classList.remove("shake");
		void unsavedBar.offsetWidth;
		unsavedBar.classList.add("shake");
		toast(t("Guarda los cambios o restablécelos antes de cerrar"), "error");
		return false;
	};
	const openSettings = (page = "account") => { showSettingsPage(page); openModal(settingsModal); };
	document.addEventListener("click", (event) => {
		const opener = event.target.closest("[data-open-settings]");
		if (opener) { openSettings(opener.dataset.openSettings); return; }
		const link = event.target.closest("[data-settings-page]");
		if (link && settingsModal.contains(link)) showSettingsPage(link.dataset.settingsPage);
		const jump = event.target.closest("[data-settings-scroll]");
		if (jump) {
			event.preventDefault();
			showSettingsPage("account");
			document.getElementById(jump.dataset.settingsScroll)?.scrollIntoView({ block: "start" });
		}
	});
	settingsModal.querySelector("[data-settings-search]")?.addEventListener("input", (event) => {
		const query = event.target.value.trim().toLowerCase();
		settingsModal.querySelectorAll(".settings-link, .settings-sub a").forEach((item) => {
			if (item.closest("form")) return;
			item.hidden = !!query && !item.textContent.toLowerCase().includes(query);
		});
	});
	const openFromHash = () => {
		const match = location.hash.match(/^#settings(?:\/(\w+))?/);
		if (!match) return;
		openSettings(match[1] || "account");
		history.replaceState(null, "", location.pathname + location.search);
	};
	openFromHash();
	window.addEventListener("hashchange", openFromHash);

	/* Inline editing rows */
	document.addEventListener("click", (event) => {
		const toggle = event.target.closest("[data-edit-toggle]");
		if (toggle) {
			const form = toggle.closest(".setting-row").querySelector(".setting-edit");
			form.hidden = !form.hidden;
			toggle.textContent = t(form.hidden ? "Editar" : "Cancelar");
			if (!form.hidden) form.querySelector("input")?.focus();
		}
		const cancel = event.target.closest("[data-edit-cancel]");
		if (cancel) {
			const row = cancel.closest(".setting-row");
			row.querySelector(".setting-edit").hidden = true;
			row.querySelector("[data-edit-toggle]").textContent = t("Editar");
		}
		const email = event.target.closest("[data-email-toggle]");
		if (email) {
			event.preventDefault();
			const span = settingsModal.querySelector("[data-email]");
			const showing = span.textContent === span.dataset.full;
			span.textContent = showing ? span.dataset.masked : span.dataset.full;
			email.textContent = t(showing ? "Mostrar" : "Ocultar");
		}
	});

	const formHandlers = {
		username: (form, data) => {
			document.querySelectorAll("[data-user-name]").forEach((el) => { el.textContent = data.username; });
			settingsModal.querySelector('[data-value="username"]').textContent = data.username;
			document.querySelectorAll("[data-user-face]").forEach((face) => { face.dataset.initial = data.username[0].toUpperCase(); if (!face.querySelector("img")) face.textContent = face.dataset.initial; });
			closeRowEditor(form);
			toast(t("Nombre de usuario actualizado"), "success");
		},
		password: (form) => { form.reset(); closeRowEditor(form); toast(t("Contraseña actualizada"), "success"); },
	};
	function closeRowEditor(form) {
		form.hidden = true;
		form.closest(".setting-row").querySelector("[data-edit-toggle]").textContent = t("Editar");
	}
	document.addEventListener("submit", async (event) => {
		const form = event.target.closest("[data-json-form]");
		if (!form) return;
		event.preventDefault();
		const errorBox = form.querySelector(".form-error");
		errorBox.hidden = true;
		const submit = form.querySelector("button:not([type=button])");
		setButtonLoading(submit, true);
		const data = await postForm(form.action, new FormData(form));
		setButtonLoading(submit, false);
		if (!data.ok) { errorBox.textContent = t(data.error || "Algo salió mal. Inténtalo de nuevo."); errorBox.hidden = false; return; }
		formHandlers[form.dataset.jsonForm]?.(form, data);
	});

	/* Two-step verification */
	document.addEventListener("click", async (event) => {
		const button = event.target.closest("[data-totp-enable]");
		if (!button) return;
		setButtonLoading(button, true);
		const data = await postForm("/profile/totp/enable", new FormData());
		if (!data.ok) { setButtonLoading(button, false); toast(t(data.error || "Algo salió mal. Inténtalo de nuevo."), "error"); return; }
		const panel = settingsModal.querySelector("[data-totp-panel]");
		panel.querySelector("[data-totp-secret]").textContent = data.secret;
		panel.querySelector("[data-totp-link]").href = data.uri;
		const qr = panel.querySelector("[data-totp-qr]");
		if (data.qr_svg) { qr.innerHTML = data.qr_svg; qr.hidden = false; }
		panel.querySelector("[data-recovery-list]").replaceChildren(...data.recovery_codes.map((code) => { const li = document.createElement("li"); const c = document.createElement("code"); c.dataset.recoveryCode = ""; c.textContent = code; li.append(c); return li; }));
		panel.hidden = false;
		settingsModal.querySelector("[data-totp-status]").textContent = t("Habilitado");
		button.remove();
	});
	document.addEventListener("click", (event) => {
		const button = event.target.closest("[data-download-recovery]");
		if (!button) return;
		const codes = [...document.querySelectorAll("[data-recovery-code]")].map((code) => code.textContent.trim()).join("\n");
		const link = document.createElement("a");
		link.href = URL.createObjectURL(new Blob([`Assignment Autopsy recovery codes\n\n${codes}\n`], { type: "text/plain" }));
		link.download = "assignment-autopsy-recovery-codes.txt";
		link.click();
		URL.revokeObjectURL(link.href);
	});

	/* Profile picture: crop → preview → save/reset bar (like Discord) */
	const savedAvatarUrl = () => settingsModal.querySelector("[data-user-face] img")?.getAttribute("src") || null;
	let originalAvatarUrl = savedAvatarUrl();
	const removeButton = settingsModal.querySelector("[data-avatar-remove]");
	settingsModal.querySelector("[data-avatar-change]")?.addEventListener("click", () => settingsModal.querySelector("[data-avatar-file]").click());
	settingsModal.addEventListener("avatar-cropped", (event) => {
		pendingAvatar = event.detail.file;
		settingsModal.querySelectorAll("[data-preview-face]").forEach((face) => renderFace(face, URL.createObjectURL(pendingAvatar)));
		unsavedBar.hidden = false;
	});
	settingsModal.querySelector("[data-avatar-reset]")?.addEventListener("click", () => {
		pendingAvatar = null;
		unsavedBar.hidden = true;
		setUserAvatar(originalAvatarUrl);
	});
	settingsModal.querySelector("[data-avatar-save]")?.addEventListener("click", async (event) => {
		if (!pendingAvatar) return;
		// `event.currentTarget` is nulled by the browser once dispatch ends, so it must be
		// captured before the `await` below or the post-save cleanup never runs.
		const button = event.currentTarget;
		setButtonLoading(button, true);
		const form = new FormData();
		form.append("avatar", pendingAvatar, pendingAvatar.name);
		const data = await postForm("/profile/avatar", form);
		setButtonLoading(button, false);
		if (!data.ok) { toast(t(data.error || "Algo salió mal. Inténtalo de nuevo."), "error"); return; }
		pendingAvatar = null;
		originalAvatarUrl = data.avatar_url;
		unsavedBar.hidden = true;
		setUserAvatar(data.avatar_url);
		toast(t("Imagen de perfil actualizada"), "success");
	});
	removeButton?.addEventListener("click", async (event) => {
		const button = event.currentTarget;
		setButtonLoading(button, true);
		const data = await postForm("/profile/avatar/remove", new FormData());
		setButtonLoading(button, false);
		if (!data.ok) { toast(t(data.error || "Algo salió mal. Inténtalo de nuevo."), "error"); return; }
		pendingAvatar = null;
		originalAvatarUrl = null;
		unsavedBar.hidden = true;
		setUserAvatar(null);
		toast(t("Imagen eliminada"), "success");
	});
	function setUserAvatar(url) {
		document.querySelectorAll("[data-user-face]").forEach((face) => renderFace(face, url));
		if (removeButton) removeButton.hidden = !url;
	}
}

/* ---- Team settings pop-up (group admin): same left-nav layout as account settings ---- */
const groupSettingsModal = document.getElementById("group-settings-modal");
if (groupSettingsModal) {
	const groupTitles = { overview: t("Resumen"), invites: t("Invitaciones"), members: t("Miembros") };
	function showGroupSettingsPage(name) {
		groupSettingsModal.querySelectorAll("[data-group-page]").forEach((page) => { page.hidden = page.dataset.groupPage !== name; });
		groupSettingsModal.querySelectorAll("[data-group-settings-page]").forEach((link) => link.classList.toggle("is-active", link.dataset.groupSettingsPage === name));
		const title = groupSettingsModal.querySelector("[data-group-settings-title]");
		if (title) title.textContent = groupTitles[name] || "";
		groupSettingsModal.querySelector(".settings-scroll").scrollTop = 0;
	}
	groupSettingsModal.addEventListener("click", (event) => {
		const link = event.target.closest("[data-group-settings-page]");
		if (link) showGroupSettingsPage(link.dataset.groupSettingsPage);
	});
	// Lets other pages (e.g. the team card's right-click menu, or a redirect after
	// generating/pausing an invite) deep-link straight into a specific tab.
	const groupHashMatch = location.hash.match(/^#group-settings(?:\/(\w+))?/);
	if (groupHashMatch) {
		showGroupSettingsPage(groupHashMatch[1] || "overview");
		openModal(groupSettingsModal);
		history.replaceState(null, "", location.pathname + location.search);
	}
}

function renderFace(face, url) {
	face.replaceChildren();
	if (url) {
		const image = new Image();
		image.alt = "";
		image.src = url;
		face.append(image);
	} else {
		face.textContent = face.dataset.initial || "";
	}
}

/* ==========================================================================
   Avatar picker + Discord-style cropper (drag to move, zoom, rotate)
   ========================================================================== */
const CROP_STAGE = 340;
const CROP_DIAMETER = 280;
const CROP_OUTPUT = 512;

function openCropper(file) {
	return new Promise((resolve) => {
		const sourceUrl = URL.createObjectURL(file);
		const image = new Image();
		image.onerror = () => { URL.revokeObjectURL(sourceUrl); toast(t("No se pudo leer la imagen"), "error"); resolve(null); };
		image.onload = () => build();
		image.src = sourceUrl;

		function build() {
			let rotation = 0;
			let zoom = 1;
			let offsetX = 0;
			let offsetY = 0;
			const backdrop = document.createElement("div");
			backdrop.className = "modal-backdrop cropper-backdrop";
			backdrop.innerHTML = `<div class="cropper-dialog" role="dialog" aria-modal="true" aria-label="${t("Editar imagen")}">
				<h3>${t("Editar imagen")}</h3>
				<div class="cropper-stage"><canvas width="${CROP_STAGE}" height="${CROP_STAGE}"></canvas><div class="cropper-mask"></div></div>
				<p class="cropper-hint">${t("Arrastra para mover la imagen")}</p>
				<div class="cropper-controls">
					<span class="cropper-zoom-icon small" aria-hidden="true">▲</span>
					<input type="range" min="1" max="4" step="0.01" value="1" aria-label="${t("Zoom")}">
					<span class="cropper-zoom-icon big" aria-hidden="true">▲</span>
					<button type="button" class="icon-button" data-rotate title="${t("Girar")}" aria-label="${t("Girar")}">⟳</button>
				</div>
				<footer><button type="button" class="button secondary" data-cancel>${t("Cancelar")}</button><button type="button" class="button" data-apply>${t("Aplicar")}</button></footer>
			</div>`;
			const stage = backdrop.querySelector(".cropper-stage");
			const canvas = backdrop.querySelector("canvas");
			const slider = backdrop.querySelector("input[type=range]");
			const context = canvas.getContext("2d");

			const geometry = () => {
				const swapped = rotation % 180 !== 0;
				const width = swapped ? image.naturalHeight : image.naturalWidth;
				const height = swapped ? image.naturalWidth : image.naturalHeight;
				const scale = (CROP_DIAMETER / Math.min(width, height)) * zoom;
				return { scale, width: width * scale, height: height * scale };
			};
			const clamp = () => {
				const g = geometry();
				const maxX = Math.max(0, (g.width - CROP_DIAMETER) / 2);
				const maxY = Math.max(0, (g.height - CROP_DIAMETER) / 2);
				offsetX = Math.min(maxX, Math.max(-maxX, offsetX));
				offsetY = Math.min(maxY, Math.max(-maxY, offsetY));
			};
			const draw = (ctx, size, factor) => {
				ctx.clearRect(0, 0, size, size);
				ctx.imageSmoothingQuality = "high";
				ctx.save();
				ctx.translate(size / 2 + offsetX * factor, size / 2 + offsetY * factor);
				ctx.rotate((rotation * Math.PI) / 180);
				const scale = geometry().scale * factor;
				ctx.scale(scale, scale);
				ctx.drawImage(image, -image.naturalWidth / 2, -image.naturalHeight / 2);
				ctx.restore();
			};
			const paint = () => { clamp(); draw(context, CROP_STAGE, 1); };

			let drag = null;
			stage.addEventListener("pointerdown", (event) => { drag = { x: event.clientX, y: event.clientY }; stage.setPointerCapture(event.pointerId); stage.classList.add("is-dragging"); });
			stage.addEventListener("pointermove", (event) => {
				if (!drag) return;
				const ratio = CROP_STAGE / stage.getBoundingClientRect().width;
				offsetX += (event.clientX - drag.x) * ratio;
				offsetY += (event.clientY - drag.y) * ratio;
				drag = { x: event.clientX, y: event.clientY };
				paint();
			});
			const endDrag = () => { drag = null; stage.classList.remove("is-dragging"); };
			stage.addEventListener("pointerup", endDrag);
			stage.addEventListener("pointercancel", endDrag);
			stage.addEventListener("wheel", (event) => {
				event.preventDefault();
				zoom = Math.min(4, Math.max(1, zoom - event.deltaY * 0.002));
				slider.value = String(zoom);
				paint();
			}, { passive: false });
			slider.addEventListener("input", () => { zoom = Number(slider.value); paint(); });
			backdrop.querySelector("[data-rotate]").addEventListener("click", () => { rotation = (rotation + 90) % 360; offsetX = 0; offsetY = 0; paint(); });

			const finish = (result) => {
				backdrop.remove();
				URL.revokeObjectURL(sourceUrl);
				if (!document.querySelector(".modal-backdrop:not([hidden])")) document.body.classList.remove("modal-open");
				resolve(result);
			};
			backdrop._close = () => finish(null);
			backdrop.querySelector("[data-cancel]").addEventListener("click", () => finish(null));
			backdrop.addEventListener("click", (event) => { if (event.target === backdrop && backdropPressed) finish(null); });
			backdrop.querySelector("[data-apply]").addEventListener("click", async () => {
				const output = document.createElement("canvas");
				output.width = CROP_OUTPUT;
				output.height = CROP_OUTPUT;
				const outputContext = output.getContext("2d");
				draw(outputContext, CROP_OUTPUT, CROP_OUTPUT / CROP_DIAMETER);
				const toBlob = (type, quality) => new Promise((done) => output.toBlob(done, type, quality));
				let blob = await toBlob("image/png");
				let name = "avatar.png";
				if (blob && blob.size > 1.5 * 1024 * 1024) {
					// Keep well under the 2 MB server limit: re-encode as JPEG on white.
					outputContext.globalCompositeOperation = "destination-over";
					outputContext.fillStyle = "#fff";
					outputContext.fillRect(0, 0, CROP_OUTPUT, CROP_OUTPUT);
					blob = await toBlob("image/jpeg", 0.9);
					name = "avatar.jpg";
				}
				finish(blob ? new File([blob], name, { type: blob.type }) : null);
			});

			document.body.append(backdrop);
			document.body.classList.add("modal-open");
			paint();
			backdrop.querySelector("[data-apply]").focus();
		}
	});
}

document.querySelectorAll("[data-avatar-picker]").forEach((picker) => {
	const trigger = picker.querySelector("[data-avatar-trigger]");
	const chooser = picker.querySelector("[data-avatar-file]");
	const output = picker.querySelector("[data-avatar-output]");
	const face = picker.querySelector(".avatar-face");
	const handle = async (file) => {
		if (!file) return;
		if (!file.type.startsWith("image/")) { toast(t("Foto no permitida"), "error"); return; }
		const cropped = await openCropper(file);
		if (!cropped) return;
		if (output) {
			const transfer = new DataTransfer();
			transfer.items.add(cropped);
			output.files = transfer.files;
		}
		renderFace(face, URL.createObjectURL(cropped));
		picker.dispatchEvent(new CustomEvent("avatar-cropped", { bubbles: true, detail: { file: cropped } }));
	};
	trigger?.addEventListener("click", () => chooser.click());
	chooser?.addEventListener("change", () => { const file = chooser.files?.[0]; chooser.value = ""; handle(file); });
	trigger?.addEventListener("dragover", (event) => event.preventDefault());
	trigger?.addEventListener("drop", (event) => { event.preventDefault(); handle(event.dataTransfer?.files?.[0]); });
});

/* ==========================================================================
   Rubric builder
   ========================================================================== */
const rubricToggle = document.querySelector("[data-rubric-toggle]");
const rubricPanel = document.querySelector("[data-rubric-panel]");
rubricToggle?.addEventListener("change", () => {
	if (rubricPanel) rubricPanel.hidden = !rubricToggle.checked;
	scheduleRubricInsertLayout();
});

const rubricGrid = document.querySelector("[data-rubric-grid]");
const rubricType = document.querySelector("[data-rubric-type]");
const rubricGridWrap = document.querySelector(".rubric-grid-wrap");

const normalizeRubricNames = () => {
	if (!rubricGrid) return;
	[...rubricGrid.tBodies[0].rows].forEach((row, rowIndex) => {
		[...row.cells].forEach((cell, columnIndex) => {
			const textarea = cell.querySelector("textarea[name^='rubric_cell_']") || cell.querySelector("textarea");
			if (textarea && columnIndex > 1) textarea.name = `rubric_cell_${rowIndex}_${columnIndex - 2}`;
		});
	});
};

const syncRubricControls = () => {
	if (!rubricGrid) return;
	normalizeRubricNames();
	[...rubricGrid.tHead.rows[0].cells].forEach((cell, index) => {
		if (index > 1) {
			cell.draggable = true;
			cell.dataset.levelIndex = String(index - 2);
			cell.classList.add("rubric-level-header");
			if (!cell.querySelector("[data-remove-column]")) {
				const remove = document.createElement("button");
				remove.type = "button";
				remove.dataset.removeColumn = "true";
				remove.className = "rubric-remove";
				remove.textContent = "×";
				remove.title = t("Eliminar nivel");
				remove.addEventListener("click", () => {
					const column = Number(cell.dataset.levelIndex) + 2;
					if (rubricGrid.tHead.rows[0].cells.length <= 3) return;
					[...rubricGrid.rows].forEach((row) => row.deleteCell(column));
					syncRubricControls();
				});
				cell.append(remove);
			}
		}
	});
	[...rubricGrid.tBodies[0].rows].forEach((row) => {
		const firstCell = row.cells[0];
		if (!firstCell.querySelector("[data-remove-row]")) {
			const remove = document.createElement("button");
			remove.type = "button";
			remove.dataset.removeRow = "true";
			remove.className = "rubric-remove rubric-row-remove";
			remove.textContent = "×";
			remove.title = t("Eliminar criterio");
			remove.addEventListener("click", () => { if (rubricGrid.tBodies[0].rows.length > 1) { row.remove(); syncRubricControls(); } });
			firstCell.append(remove);
		}
	});
	scheduleRubricInsertLayout();
};

/** Insert a brand-new criterion row at `index` (0 = above everything). */
const insertRubricRowAt = (index) => {
	if (!rubricGrid) return;
	const body = rubricGrid.tBodies[0];
	const levelCount = Math.max(0, rubricGrid.tHead.rows[0].cells.length - 2);
	const cells = Array.from({ length: levelCount }, () => `<td><textarea placeholder="${t('Describe este nivel...')}"></textarea></td>`).join("");
	const row = document.createElement("tr");
	row.innerHTML = `<td><input name="criterion_label" placeholder="${t('Nuevo criterio')}"></td><td class="points-column"><input name="criterion_points" type="number" min="0" placeholder="-"></td>${cells}`;
	body.insertBefore(row, body.rows[index] || null);
	syncRubricControls();
	updateGradePreview();
};

/** Insert a brand-new level column at `index` (0 = leftmost level). */
const insertRubricColumnAt = (index) => {
	if (!rubricGrid) return;
	const headRow = rubricGrid.tHead.rows[0];
	const headPosition = index + 2;
	const isPoints = rubricType && rubricType.value === "points";
	const heading = document.createElement("th");
	heading.innerHTML = `<input name="level_label" value="${isPoints ? index : `Nivel ${index + 1}`}" placeholder="${t('Nuevo nivel')}">`;
	headRow.insertBefore(heading, headRow.cells[headPosition] || null);
	[...rubricGrid.tBodies[0].rows].forEach((row) => {
		const cell = document.createElement("td");
		cell.innerHTML = `<textarea placeholder="${t('Describe este nivel...')}"></textarea>`;
		row.insertBefore(cell, row.cells[headPosition] || null);
	});
	syncRubricControls();
	updateGradePreview();
};

document.querySelector("[data-add-rubric-row]")?.addEventListener("click", () => {
	if (!rubricGrid) return;
	insertRubricRowAt(rubricGrid.tBodies[0].rows.length);
});
document.querySelector("[data-add-rubric-column]")?.addEventListener("click", () => {
	if (!rubricGrid) return;
	insertRubricColumnAt(rubricGrid.tHead.rows[0].cells.length - 2);
});

/* ---- Word-style hover "+" seams for inserting a row/column in place ---- */
let rubricLayoutHandle = null;
function scheduleRubricInsertLayout() {
	if (!rubricGridWrap || !rubricGrid) return;
	if (rubricLayoutHandle) cancelAnimationFrame(rubricLayoutHandle);
	rubricLayoutHandle = requestAnimationFrame(layoutRubricInsertZones);
}

function layoutRubricInsertZones() {
	if (!rubricGridWrap || !rubricGrid || rubricGridWrap.clientWidth === 0) return;
	rubricGridWrap.querySelectorAll(".rubric-insert-row, .rubric-insert-col").forEach((el) => el.remove());
	const wrapRect = rubricGridWrap.getBoundingClientRect();
	const body = rubricGrid.tBodies[0];
	const rows = [...body.rows];

	const rowSeams = [];
	if (rows.length) {
		const firstTop = rows[0].getBoundingClientRect().top - wrapRect.top + rubricGridWrap.scrollTop;
		rowSeams.push({ y: firstTop, index: 0, label: t("Insertar criterio arriba") });
		rows.forEach((row, i) => {
			const bottom = row.getBoundingClientRect().bottom - wrapRect.top + rubricGridWrap.scrollTop;
			rowSeams.push({ y: bottom, index: i + 1, label: t("Insertar criterio aquí") });
		});
	}
	rowSeams.forEach(({ y, index, label }) => {
		const zone = document.createElement("div");
		zone.className = "rubric-insert-row";
		zone.style.top = `${y - 7}px`;
		zone.title = label;
		zone.innerHTML = '<span class="rubric-insert-bubble" aria-hidden="true">+</span>';
		zone.addEventListener("click", () => insertRubricRowAt(index));
		rubricGridWrap.appendChild(zone);
	});

	const headCells = [...rubricGrid.tHead.rows[0].cells];
	const levelCells = headCells.filter((_, i) => i > 1);
	const colSeams = [];
	if (levelCells.length) {
		const firstLeft = levelCells[0].getBoundingClientRect().left - wrapRect.left + rubricGridWrap.scrollLeft;
		colSeams.push({ x: firstLeft, index: 0, label: t("Insertar nivel a la izquierda") });
		levelCells.forEach((cell, i) => {
			const right = cell.getBoundingClientRect().right - wrapRect.left + rubricGridWrap.scrollLeft;
			colSeams.push({ x: right, index: i + 1, label: t("Insertar nivel aquí") });
		});
	}
	colSeams.forEach(({ x, index, label }) => {
		const zone = document.createElement("div");
		zone.className = "rubric-insert-col";
		zone.style.left = `${x - 7}px`;
		zone.title = label;
		zone.innerHTML = '<span class="rubric-insert-bubble" aria-hidden="true">+</span>';
		zone.addEventListener("click", () => insertRubricColumnAt(index));
		rubricGridWrap.appendChild(zone);
	});
}

if (rubricGrid && rubricGridWrap && "ResizeObserver" in window) {
	const rubricResizeObserver = new ResizeObserver(() => scheduleRubricInsertLayout());
	rubricResizeObserver.observe(rubricGrid);
	rubricResizeObserver.observe(rubricGridWrap);
}
window.addEventListener("resize", scheduleRubricInsertLayout);
rubricGridWrap?.addEventListener("scroll", () => { /* absolutely-positioned seams scroll with the content already */ });

const rubricOrderToggle = document.querySelector("[data-rubric-order-toggle]");
const rubricDescending = document.querySelector("[data-rubric-descending]");
const rubricOrderLabel = document.querySelector("[data-rubric-order-label]");
const rubricOrderHint = document.querySelector("[data-rubric-order-hint]");
const syncRubricOrderVisibility = () => {
	const isLevel = !rubricType || rubricType.value === "level";
	if (rubricOrderToggle) rubricOrderToggle.hidden = !isLevel;
	if (rubricOrderHint) rubricOrderHint.hidden = !isLevel;
};
rubricType?.addEventListener("change", () => {
	if (rubricType.value !== "points" || !rubricGrid) return;
	[...rubricGrid.tHead.rows[0].cells].forEach((cell, index) => { if (index > 1) { const input = cell.querySelector("input[name='level_label']"); if (input) input.value = String(index - 1); } });
});
rubricDescending?.addEventListener("change", () => {
	if (rubricOrderLabel) rubricOrderLabel.textContent = rubricDescending.checked ? t("Ordenado de mayor a menor") : t("Ordenado de menor a mayor");
});
rubricType?.addEventListener("change", syncRubricOrderVisibility);
syncRubricOrderVisibility();

rubricGrid?.addEventListener("dragstart", (event) => { if (event.target.closest("th")) event.dataTransfer.setData("text/plain", event.target.closest("th").dataset.levelIndex); });
rubricGrid?.addEventListener("dragover", (event) => { if (event.target.closest("th.rubric-level-header")) event.preventDefault(); });
rubricGrid?.addEventListener("drop", (event) => {
	const target = event.target.closest("th.rubric-level-header");
	if (!target) return;
	event.preventDefault();
	const sourceIndex = Number(event.dataTransfer.getData("text/plain"));
	const targetIndex = Number(target.dataset.levelIndex);
	if (sourceIndex === targetIndex || Number.isNaN(sourceIndex)) return;
	const sourceColumn = sourceIndex + 2;
	const targetColumn = targetIndex + 2;
	[...rubricGrid.rows].forEach((row) => { const sourceCell = row.cells[sourceColumn]; const targetCell = row.cells[targetColumn]; if (sourceIndex < targetIndex) row.insertBefore(targetCell, sourceCell); else row.insertBefore(sourceCell, targetCell); });
	syncRubricControls();
});
syncRubricControls();

const firstName = document.querySelector("[data-name][name='first_name']");
const lastName = document.querySelector("[data-name][name='last_name']");
const username = document.querySelector("[data-username]");
const suggestions = document.querySelector("[data-suggestions]");
const suggestUsernames = () => {
	if (!firstName || !lastName || !username || !suggestions) return;
	const clean = (value) => value.toLowerCase().replace(/[^a-z0-9]/g, "");
	const first = clean(firstName.value);
	const last = clean(lastName.value);
	const values = [...new Set([`${first}.${last}`, `${first}${last}`, `${first}_${last}`, `${first}${last}01`])].filter((value) => value && value.length <= 30);
	suggestions.replaceChildren(...values.map((value) => {
		const button = document.createElement("button");
		button.type = "button";
		button.className = "username-suggestion";
		button.textContent = value;
		button.addEventListener("click", () => { username.value = value; });
		return button;
	}));
};
firstName?.addEventListener("input", suggestUsernames);
lastName?.addEventListener("input", suggestUsernames);

const gradingForm = document.querySelector("[data-rubric-grading]");
function updateGradePreview() {
	if (!gradingForm) return;
	const earnedEl = gradingForm.querySelector("[data-preview-earned]");
	const maxEl = gradingForm.querySelector("[data-preview-max]");
	if (!earnedEl || !maxEl) return;
	const descending = gradingForm.dataset.rubricDescending === "1";
	const levelCount = Number(gradingForm.dataset.levelCount || 0);
	let earned = 0;
	let max = 0;
	gradingForm.querySelectorAll("[data-rubric-choice]").forEach((select) => {
		const row = select.closest("[data-max-points]");
		const rowMax = Number(row?.dataset.maxPoints || 0);
		max += rowMax;
		const option = select.selectedOptions[0];
		if (!option || option.value === "" || !levelCount) return;
		const position = Number(option.dataset.position);
		const rank = descending ? levelCount - position : position + 1;
		earned += rowMax * (rank / levelCount);
	});
	gradingForm.querySelectorAll("[data-rubric-points]").forEach((input) => {
		const rowMax = Number(input.dataset.maxPoints || 0);
		max += rowMax;
		const value = Number(input.value || 0);
		earned += Math.max(0, Math.min(value, rowMax));
	});
	earnedEl.textContent = Math.round(earned * 100) / 100;
	maxEl.textContent = Math.round(max * 100) / 100;
}
gradingForm?.addEventListener("change", updateGradePreview);
gradingForm?.addEventListener("input", updateGradePreview);
updateGradePreview();

document.querySelectorAll("[data-sortable-table]").forEach((table) => {
	table.querySelectorAll("[data-sort-button]").forEach((button) => {
		button.addEventListener("click", () => {
			const header = button.closest("th");
			const key = header.dataset.sortKey;
			const type = header.dataset.sortType || "text";
			const ascending = header.dataset.sortDirection !== "asc";
			table.querySelectorAll("th").forEach((th) => delete th.dataset.sortDirection);
			header.dataset.sortDirection = ascending ? "asc" : "desc";
			const body = table.tBodies[0];
			const rows = [...body.rows];
			rows.sort((a, b) => {
				const rawA = a.dataset[key] ?? "";
				const rawB = b.dataset[key] ?? "";
				const valueA = type === "number" ? Number(rawA) : rawA;
				const valueB = type === "number" ? Number(rawB) : rawB;
				if (valueA < valueB) return ascending ? -1 : 1;
				if (valueA > valueB) return ascending ? 1 : -1;
				return 0;
			});
			rows.forEach((row) => body.append(row));
		});
	});
});
