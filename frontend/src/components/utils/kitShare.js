import Swal from "sweetalert2";

export function getCanonicalKitUrl(item) {
	const owner = item?.owner_username?.trim();
	const kitId = item?.id;

	if (!owner || !kitId) return "";

	return `${window.location.origin}/profile/${owner}/kits/${kitId}`;
}

export async function copyKitShareUrl(item) {
	const canonicalUrl = getCanonicalKitUrl(item);

	if (!canonicalUrl) {
		Swal.fire("Error", "Could not build a link for this kit.", "error");
		return false;
	}

	if (!navigator.clipboard?.writeText) {
		Swal.fire({
			title: "Share",
			text: canonicalUrl,
			icon: "info",
		});
		return true;
	}

	try {
		await navigator.clipboard.writeText(canonicalUrl);
		Swal.fire("Copied", "Kit link copied.", "success");
		return true;
	} catch (error) {
		console.error("Failed to copy kit link", error);
		Swal.fire({
			title: "Share",
			text: canonicalUrl,
			icon: "info",
		});
		return true;
	}
}
