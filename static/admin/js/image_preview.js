document.addEventListener("change", function (e) {
    if (e.target.type === "file" && e.target.name.includes("image")) {
        const input = e.target;
        const file = input.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (evt) {
            let preview = input.closest("td").querySelector("img");

            if (!preview) {
                preview = document.createElement("img");
                preview.style.width = "100px";
                preview.style.height = "70px";
                preview.style.objectFit = "cover";
                preview.style.border = "1px solid #ddd";
                preview.style.borderRadius = "6px";
                preview.style.marginTop = "6px";
                input.closest("td").appendChild(preview);
            }
            preview.src = evt.target.result;
        };
        reader.readAsDataURL(file);
    }
});
