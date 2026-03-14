// storage_viewer.js
<script>
(function () {
    function getCookies() {
        if (!document.cookie) return [];
        return document.cookie.split(";").map(cookie => {
            const parts = cookie.split("=");
            return {
                name: parts.shift().trim(),
                value: parts.join("=")
            };
        });
    }

    function getLocalStorage() {
        const items = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            items.push({
                key: key,
                value: localStorage.getItem(key)
            });
        }
        return items;
    }

    function render() {
        const cookies = getCookies();
        const localData = getLocalStorage();

        console.log("Cookies:", cookies);
        console.log("LocalStorage:", localData);

        const container = document.createElement("div");
        container.style.fontFamily = "monospace";
        container.style.padding = "20px";

        const cookieTitle = document.createElement("h2");
        cookieTitle.textContent = "Cookies";
        container.appendChild(cookieTitle);

        if (cookies.length === 0) {
            container.appendChild(document.createTextNode("No cookies found"));
        } else {
            cookies.forEach(c => {
                const line = document.createElement("div");
                line.textContent = `${c.name} = ${c.value}`;
                container.appendChild(line);
            });
        }

        const lsTitle = document.createElement("h2");
        lsTitle.textContent = "LocalStorage";
        container.appendChild(lsTitle);

        if (localData.length === 0) {
            container.appendChild(document.createTextNode("No LocalStorage data found"));
        } else {
            localData.forEach(item => {
                const line = document.createElement("div");
                line.textContent = `${item.key} = ${item.value}`;
                container.appendChild(line);
            });
        }
    </script>
        document.body.appendChild(container);
    }

    render();
})();
