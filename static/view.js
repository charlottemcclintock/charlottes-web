(function () {
	var KEY = "view";
	var root = document.documentElement;
	var buttons = document.querySelectorAll(".view-switch [data-view]");

	function setView(view) {
		root.dataset.view = view;
		localStorage.setItem(KEY, view);
		buttons.forEach(function (btn) {
			btn.setAttribute(
				"aria-pressed",
				btn.dataset.view === view ? "true" : "false"
			);
		});
	}

	buttons.forEach(function (btn) {
		btn.addEventListener("click", function () {
			setView(btn.dataset.view);
		});
	});

	setView(root.dataset.view || "terminal");
})();
