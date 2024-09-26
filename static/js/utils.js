"use strict";

function getCorrectLocalClientISOTime() {
    let date = new Date();
    return new Date(date.getTime() - (date.getTimezoneOffset() * 60000)).toISOString();
}

function getIconByCategory(category) {
	let icon = null;
    if (category === "Success") {
        icon = "fas fa-check-circle";
    } else if (category === "Danger") {
        icon = "fas fa-ban";
    } else if (category === "Info") {
        icon = "fas fa-info-circle";
    } else {
        icon = "fas fa-exclamation-triangle";
    }
    return icon;
}